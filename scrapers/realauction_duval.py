"""Duval RealAuction adapter — foreclosure + tax-deed sales (PRIMARY EVENTS).

Source ids   : realforeclose_duval   (https://duval.realforeclose.com)
               realtaxdeed_duval     (https://duval.realtaxdeed.com)
Role         : PRIMARY_LEAD_SOURCE / PRIMARY_EVENT_SOURCE.

Ported from the operator's existing surplusiq project
(xcerebroai/surplusiq — core/auction/universal.py). RealAuction is NOT a
login wall — the splash-page login chrome lives at /index.cfm, but the
auction calendar items render at the date-direct URL:

    /index.cfm?zaction=AUCTION&Zmethod=PREVIEW&AUCTIONDATE=MM/DD/YYYY

No AUCTIONDAYID harvest needed; this URL renders the day's auction items
directly. Stealthy Chromium (slow_mo=250, AutomationControlled disabled,
real desktop UA + viewport) reaches it cleanly.

Output: §4.32 wrapped raw_record per sale → data/raw/<source_id>.jsonl.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

REPO_ROOT = Path(__file__).resolve().parents[1]

USER_AGENT = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
              "AppleWebKit/537.36 (KHTML, like Gecko) "
              "Chrome/124.0.0.0 Safari/537.36")
NAV_TIMEOUT_MS = 35000
SETTLE_MS = 3500

PORTALS = {
    "realforeclose": {
        "source_id": "realforeclose_duval",
        "base_url": "https://www.duval.realforeclose.com",
        "doc_type_raw": "FORECLOSURE SALE",
        "canonical_doc_type": "notice_of_sale",
    },
    "realtaxdeed": {
        "source_id": "realtaxdeed_duval",
        "base_url": "https://www.duval.realtaxdeed.com",
        "doc_type_raw": "TAX DEED SALE",
        "canonical_doc_type": "tax_deed",
    },
}

POSITIVE_PAGE_MARKERS = (
    "Preview Items For Sale", "Auction Sold", "Auction Status",
    "Case #", "Opening Bid", "Sold To", "3rd Party Bidder",
    "Plaintiff Max Bid", "Final Judgment Amount", "Assessed Value",
)

ITEM_SELECTORS = (
    "div.AUCTION_ITEM", "div.AITEM", "[id^='Area_W']",
    "[class*='auction-item']", "div.auctionItem",
)

# Duval mortgage case format: 16-2024-CA-006388.
# Tax deed case format: 2025-0464TD.
DUVAL_MORTGAGE_CASE_RE = re.compile(r"\b(16-\d{4}-[A-Z]{2,4}-\d{4,8})\b")
DUVAL_TAXDEED_CASE_RE = re.compile(r"\b(\d{4}-\d{3,5}TD)\b", re.I)

ADDRESS_STREET_TYPES = (
    r"ST|AVE|AVENUE|BLVD|BOULEVARD|DR|DRIVE|RD|ROAD|LN|LANE|"
    r"CT|COURT|WAY|PL|PLACE|CIR|CIRCLE|HWY|HIGHWAY|TRL|TRAIL|"
    r"PKWY|PARKWAY|TER|TERRACE|STREET"
)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def _money(s) -> float:
    if not s:
        return 0.0
    try:
        return float(re.sub(r"[^\d.]", "", str(s)))
    except (ValueError, TypeError):
        return 0.0


def _is_valid_auction_page(html: str) -> bool:
    if len(html) < 3000:
        return False
    if ("KNOWING THERE IS NO GUARANTEE" in html.upper()
            and "AUCTION" not in html[:2000].upper()):
        return False
    return any(marker in html for marker in POSITIVE_PAGE_MARKERS)


def _extract_field(text: str, field_names: list[str]) -> str:
    """Extract 'Field: value' or 'Field:\\n value'. Matches universal.py."""
    for field in field_names:
        pat = rf"{re.escape(field)}\s*:?\s*\n\s*([^\n]+)"
        m = re.search(pat, text, re.IGNORECASE)
        if m:
            return m.group(1).strip()
        pat = rf"{re.escape(field)}\s*:?\s*([^\n]+)"
        m = re.search(pat, text, re.IGNORECASE)
        if m:
            val = m.group(1).strip()
            val = re.split(r"(?=[A-Z][a-z]+\s*#|:)", val)[0].strip()
            if val:
                return val
    return ""


def _extract_address(text: str) -> str:
    for line in text.split("\n"):
        line = line.strip()
        if re.search(rf"\d+.*\b({ADDRESS_STREET_TYPES})\b", line, re.I):
            return line
    return ""


def _setup_browser(p, headless: bool = True):
    browser = p.chromium.launch(
        headless=headless,
        slow_mo=250,
        args=[
            "--no-sandbox",
            "--disable-blink-features=AutomationControlled",
            "--disable-features=IsolateOrigins,site-per-process",
        ],
    )
    ctx = browser.new_context(
        user_agent=USER_AGENT,
        viewport={"width": 1400, "height": 900},
        locale="en-US",
        timezone_id="America/New_York",
    )
    return browser, ctx, ctx.new_page()


def _parse_item_text(text: str, *, auction_date: date, case_re,
                     doc_type_raw: str, base_url: str, day_str: str) -> Optional[dict]:
    """Parse one auction item's inner_text. Returns wrapped raw_payload or None."""
    if len(text) < 30:
        return None
    # Case number — try labelled first, then regex.
    case_num = _extract_field(text, ["Case #", "Case Number", "Case"]) or ""
    case_num = case_num.strip()
    if not case_num:
        m = case_re.search(text)
        if m:
            case_num = m.group(1)
    if not case_num:
        return None
    # Status detection.
    status = _extract_field(text, ["Auction Status"]) or ""
    if not status:
        if "Auction Sold" in text:        status = "Sold"
        elif "Auction Redeemed" in text:  status = "Redeemed"
        elif "Cancel" in text:            status = "Canceled"
        elif "Postponed" in text:         status = "Postponed"
        elif "Bankruptcy" in text:        status = "Bankruptcy"
        elif "Withdrawn" in text:         status = "Withdrawn"
        elif "Waiting" in text:           status = "Waiting"
    # Money fields.
    opening = _money(_extract_field(text, [
        "Opening Bid", "Final Judgment Amount", "Judgment Amount",
        "Plaintiff Max Bid",
    ]))
    final_sale = _money(_extract_field(text, [
        "Amount", "Sold Amount", "Winning Bid",
    ]))
    assessed = _money(_extract_field(text, ["Assessed Value"]))
    if not final_sale:
        dollars = sorted([_money(d) for d in re.findall(
            r"\$([\d,]+(?:\.\d{2})?)", text)
            if _money(d) > 500])
        if dollars:
            final_sale = dollars[-1]
            if not opening and len(dollars) >= 2:
                opening = dollars[-2]
    sold_to = _extract_field(text, ["Sold To", "Winner", "Bidder"]) or ""
    auction_type = _extract_field(text, ["Auction Type", "Type"]) or ""
    cert_num = _extract_field(text, ["Certificate #", "Certificate"]) or ""
    parcel_id = _extract_field(text, ["Parcel ID", "Parcel"]) or ""
    address = _extract_address(text)
    return {
        "case_number": case_num.strip(),
        "instrument_number": case_num.strip(),
        "certificate_number": cert_num.strip(),
        "auction_type": auction_type.strip(),
        "auction_status": status,
        "opening_bid": opening,
        "final_sale_price": final_sale,
        "assessed_value": assessed,
        "sold_to": sold_to.strip(),
        "parcel_id": parcel_id.strip(),
        "property_address": address,
        "doc_type": doc_type_raw,
        "auction_date": auction_date.isoformat(),
        "sale_date": auction_date.isoformat(),
        "auction_date_url": day_str,
        "extraction_method": "dom",
        "raw_text": text[:1500],
        "county": "Duval",
        "state": "FL",
    }


def _regex_fallback(html: str, *, auction_date: date, case_re,
                    doc_type_raw: str, base_url: str, day_str: str) -> list[dict]:
    """Fallback regex extraction over the raw page HTML."""
    out: list[dict] = []
    seen: set[str] = set()
    # Loose: case# anywhere, then up to ~600 chars of context.
    for m in case_re.finditer(html):
        case = m.group(1)
        if case in seen:
            continue
        seen.add(case)
        # Take a 1500-char window around the case to extract details.
        start = max(0, m.start() - 200)
        end = min(len(html), m.start() + 1500)
        chunk = html[start:end]
        chunk_text = re.sub(r"<[^>]+>", " ", chunk)
        chunk_text = re.sub(r"&nbsp;", " ", chunk_text)
        chunk_text = re.sub(r"\s+", " ", chunk_text).strip()
        parsed = _parse_item_text(chunk_text, auction_date=auction_date,
                                  case_re=case_re, doc_type_raw=doc_type_raw,
                                  base_url=base_url, day_str=day_str)
        if parsed:
            parsed["extraction_method"] = "regex_fallback"
            out.append(parsed)
    return out


def scrape_one_date(page, base_url: str, d: date, doc_type_raw: str,
                    case_re) -> tuple[list[dict], str]:
    """Scrape one auction date. Returns (list of raw_payload dicts, page_status)."""
    day_str = d.strftime("%m/%d/%Y")
    url = (f"{base_url}/index.cfm?zaction=AUCTION&Zmethod=PREVIEW"
           f"&AUCTIONDATE={day_str}")
    try:
        page.goto(url, timeout=NAV_TIMEOUT_MS, wait_until="domcontentloaded")
        page.wait_for_timeout(SETTLE_MS)
    except Exception:
        return [], "nav_error"
    html = page.content()
    if not _is_valid_auction_page(html):
        return [], "invalid_page"
    items = []
    for sel in ITEM_SELECTORS:
        items = page.query_selector_all(sel)
        if items:
            break
    sales: list[dict] = []
    if items:
        for item in items:
            try:
                text = (item.inner_text() or "").strip()
                parsed = _parse_item_text(
                    text, auction_date=d, case_re=case_re,
                    doc_type_raw=doc_type_raw, base_url=base_url,
                    day_str=day_str)
                if parsed:
                    sales.append(parsed)
            except Exception:
                continue
    if not sales:
        sales = _regex_fallback(html, auction_date=d, case_re=case_re,
                                doc_type_raw=doc_type_raw, base_url=base_url,
                                day_str=day_str)
    return sales, ("ok" if sales else "no_items")


def normalize_to_wrapped(payload: dict, *, source_id: str,
                          base_url: str, canonical: str) -> dict:
    case_no = (payload.get("case_number") or "").strip()
    day_str = payload.get("auction_date_url") or ""
    detail_url = (f"{base_url}/index.cfm?zaction=AUCTION&Zmethod=PREVIEW"
                  f"&AUCTIONDATE={day_str}" if day_str else "")
    return {
        "raw_record_id": f"{source_id}:{case_no or payload.get('certificate_number') or 'sale-' + day_str}",
        "source_id": source_id,
        "source_url": detail_url,
        "source_fetched_at": _now_iso(),
        "parser_confidence": 95 if case_no else 60,
        "raw_payload": payload,
    }


def pull(*, portal: str, days_back: int = 14, days_forward: int = 30,
         headless: bool = True, output_path: Optional[Path] = None) -> dict:
    if portal not in PORTALS:
        return {"status": "ERROR", "error": f"unknown portal {portal!r}"}
    cfg = PORTALS[portal]
    source_id = cfg["source_id"]
    base_url = cfg["base_url"]
    doc_type_raw = cfg["doc_type_raw"]
    canonical = cfg["canonical_doc_type"]
    case_re = (DUVAL_TAXDEED_CASE_RE if portal == "realtaxdeed"
               else DUVAL_MORTGAGE_CASE_RE)
    out = output_path or REPO_ROOT / "data/raw" / f"{source_id}.jsonl"
    out.parent.mkdir(parents=True, exist_ok=True)

    try:
        from playwright.sync_api import sync_playwright
    except ImportError as e:
        return {"status": "ERROR", "error": f"playwright not installed: {e}"}

    today = date.today()
    date_range = [today + timedelta(days=delta)
                  for delta in range(-days_back, days_forward + 1)]

    sales: list[dict] = []
    per_day_status: dict[str, str] = {}
    valid_days = 0

    try:
        with sync_playwright() as p:
            browser, ctx, page = _setup_browser(p, headless=headless)
            try:
                # Establish session by visiting the home page first.
                try:
                    page.goto(base_url + "/index.cfm",
                              timeout=NAV_TIMEOUT_MS,
                              wait_until="domcontentloaded")
                    page.wait_for_timeout(2500)
                except Exception:
                    pass

                for d in date_range:
                    day_sales, status = scrape_one_date(
                        page, base_url, d, doc_type_raw, case_re)
                    per_day_status[d.isoformat()] = status
                    if status == "ok":
                        valid_days += 1
                    sales.extend(day_sales)
            finally:
                browser.close()
    except Exception as e:
        return {"status": "ERROR",
                "source_id": source_id, "error": f"{type(e).__name__}: {e}",
                "per_day_status": per_day_status}

    # De-dup by case number (or certificate number for tax deeds).
    by_key: dict[str, dict] = {}
    for s in sales:
        key = (s.get("case_number") or s.get("certificate_number")
               or s.get("auction_date_url") or "").strip()
        if not key:
            continue
        prev = by_key.get(key)
        if prev is None:
            by_key[key] = s
        else:
            # Prefer the row with more populated fields.
            score_p = sum(1 for k in ("property_address", "sold_to",
                                       "final_sale_price", "parcel_id")
                          if prev.get(k))
            score_s = sum(1 for k in ("property_address", "sold_to",
                                       "final_sale_price", "parcel_id")
                          if s.get(k))
            if score_s > score_p:
                by_key[key] = s
    unique = list(by_key.values())

    tmp = out.with_suffix(".jsonl.tmp")
    with open(tmp, "w", encoding="utf-8") as fh:
        for s in unique:
            rec = normalize_to_wrapped(
                s, source_id=source_id, base_url=base_url,
                canonical=canonical)
            fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
    tmp.replace(out)

    return {
        "status": "OK",
        "source_id": source_id,
        "portal_base": base_url,
        "days_walked": len(date_range),
        "valid_auction_days": valid_days,
        "raw_sales": len(sales),
        "unique_records_written": len(unique),
        "per_day_status_sample": dict(list(per_day_status.items())[:6]),
        "output_path": str(out.relative_to(REPO_ROOT)),
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Duval RealAuction adapter — foreclosure + tax-deed sales")
    parser.add_argument("--portal", choices=list(PORTALS.keys()), required=True)
    parser.add_argument("--days-back", type=int, default=14)
    parser.add_argument("--days-forward", type=int, default=30)
    parser.add_argument("--headed", action="store_true")
    parser.add_argument("--out", default=None)
    args = parser.parse_args()

    stats = pull(portal=args.portal,
                 days_back=args.days_back,
                 days_forward=args.days_forward,
                 headless=not args.headed,
                 output_path=Path(args.out) if args.out else None)
    print(json.dumps(stats, indent=2))
    return 0 if stats.get("status") == "OK" else 1


if __name__ == "__main__":
    raise SystemExit(main())
