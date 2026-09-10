import os
import time
import json
import re
from datetime import date
from typing import List, Dict, Tuple

import pandas as pd
from lxml import html

from define_collection_wave import folder
from helpers import create_folder, setup_driver

from selenium.webdriver.common.by import By
from selenium.common.exceptions import StaleElementReferenceException, ElementClickInterceptedException, NoSuchElementException

import requests


REST_NAME = 'Cafe Rouge'
LANDING_URL = 'https://www.caferouge.com/restaurants/Center-Parcs/elveden/menu'
BASE_DOMAIN = 'https://www.caferouge.com'

# Outputs
path_out = create_folder('82_CafeRouge', folder)
file_json = os.path.join(path_out, 'cafe_rouge_items.json')
file_jsonl = os.path.join(path_out, 'cafe_rouge_items_JSONL.json')
file_csv = os.path.join(path_out, 'cafe_rouge_items.csv')


def log(msg: str):
    print(f"[CafeRouge] {msg}")


def get_text(node, xpath_expr: str) -> str:
    try:
        res = node.xpath(xpath_expr)
        if not res:
            return ''
        val = res[0] if isinstance(res, list) else res
        if hasattr(val, 'text_content'):
            return val.text_content().strip()
        return str(val).strip()
    except Exception:
        return ''


def accept_cookies(driver) -> bool:
    try:
        for xp in [
            "//button[contains(translate(., 'ACCEPT', 'accept'),'accept')]",
            "//button[contains(., 'Accept All')]",
            "//button[contains(., 'Accept')]",
            "//a[contains(., 'Accept All')]",
        ]:
            btns = driver.find_elements(By.XPATH, xp)
            for b in btns:
                try:
                    driver.execute_script("arguments[0].click();", b)
                    time.sleep(0.5)
                    log("Accepted cookies")
                    return True
                except Exception:
                    continue
    except Exception:
        pass
    return False


def navigate_to_menu_if_present(driver):
    """If a visible 'MENU' link/button exists on the page, click it to load detailed menus."""
    try:
        elems = driver.find_elements(By.XPATH, "//a[contains(@href, '/menu') or contains(translate(., 'MENU', 'menu'),'menu')] | //button[contains(translate(., 'MENU', 'menu'),'menu')]")
        for el in elems:
            try:
                driver.execute_script("arguments[0].click();", el)
                time.sleep(1.0)
                log("Clicked a MENU link/button")
                return
            except Exception:
                continue
    except Exception:
        pass


def parse_page_source(page_source: str) -> List[Dict]:
    tree = html.fromstring(page_source)
    items: List[Dict] = []
    seen: set[Tuple[str, str, str]] = set()

    # Candidate item containers: around nodes with £, or blocks with headings and price somewhere inside
    candidates = set()
    for node in tree.xpath("//*[contains(text(),'£')]"):
        # climb to nearest container div/li/article
        container = node.xpath("ancestor::*[self::div or self::li or self::article][1]")
        if container:
            candidates.add(container[0])
    # Also take common card/menu blocks with headings
    for node in tree.xpath("//div[contains(@class,'menu') or contains(@class,'card') or contains(@class,'dish')][.//*[contains(text(),'£') or .//h3 or .//h4]] | //li[.//h3 or .//h4]"):
        candidates.add(node)
    candidates = list(candidates)
    log(f"Found {len(candidates)} candidate item blocks")

    for node in candidates:
        name = (
            get_text(node, 'normalize-space(.//h3[1]/text())')
            or get_text(node, 'normalize-space(.//h4[1]/text())')
            or get_text(node, 'normalize-space(.//h2[1]/text())')
            or get_text(node, 'normalize-space(.//*[contains(@class,"title")][1]/text())')
            or get_text(node, 'normalize-space(.//strong[1]/text())')
        )
        if not name:
            continue
        # Try first paragraph; fallback to any block of text under a description-like class
        desc = (
            get_text(node, 'normalize-space(.//p[1]/text())')
            or get_text(node, 'normalize-space(.//*[contains(@class, "desc") or contains(@class, "description")][1])')
        )
        # First descendant text containing a pound sign
        price_nodes = node.xpath(".//*[contains(text(),'£')]/text()|.//text()[contains(.,'£')]")
        price = ''
        for t in price_nodes:
            t = (t or '').strip()
            if '£' in t and len(t) <= 20:
                price = t
                break
        # Nearest preceding section heading
        section = get_text(node, "(preceding::h2 | preceding::h3 | preceding::h1)[last()]/text()")

        key = (name, section, price)
        if key in seen:
            continue
        seen.add(key)

        item = {
            'rest_name': REST_NAME,
            'collection_date': date.today().strftime('%b-%d-%Y'),
            'item_name': name,
            'item_description': desc,
            'menu_section': section or '',
        }
        if price:
            item['price'] = price
        items.append(item)

    # Light sanity filter: drop obvious non-food blocks lacking description and price
    if len(items) > 0:
        filtered = [it for it in items if it.get('price') or (it.get('item_description') and len(it['item_description']) >= 4)]
        if len(filtered) != len(items):
            log(f"Filtered out {len(items)-len(filtered)} weak items")
        items = filtered

    return items


def parse_dom_sections(page_source: str) -> List[Dict]:
    """Additional DOM parsing strategy: walk section headings and capture item blocks between them.
    Heuristic: Section heading tags (h2/h3/h4) define boundaries; items are list elements, divs, or paragraphs containing a name and optional price.
    """
    tree = html.fromstring(page_source)
    items: List[Dict] = []
    headings = tree.xpath("//h2|//h3|//h4")
    for idx, h in enumerate(headings):
        try:
            section = (h.text_content() or '').strip()
            if not section or len(section) > 60:
                continue
            # Skip headings that look like marketing slogans rather than menu sections
            low = section.lower()
            if any(bad in low for bad in ['welcome', 'book', 'newsletter']):
                continue
            # Determine boundary: nodes until next heading of same set
            following = []
            limit = headings[idx + 1] if idx + 1 < len(headings) else None
            cursor = h.getparent()
            # Collect siblings after the heading within same parent first
            collected = []
            # Simple approach: take following siblings until next heading encountered
            sib = h.getnext()
            while sib is not None and sib is not limit:
                collected.append(sib)
                # stop if we encounter another heading tag
                tag = sib.tag.lower() if hasattr(sib, 'tag') and sib.tag else ''
                if tag in ('h2', 'h3', 'h4'):
                    break
                sib = sib.getnext()
            # Fallback: if nothing collected, look deeper inside parent
            if not collected:
                collected = h.xpath("following-sibling::*[position()<6]")  # arbitrary small window
            # Scan collected nodes for potential items
            for node in collected:
                # Item name candidates
                name_candidates = node.xpath(".//h3/text() | .//h4/text() | .//strong/text() | ./text()")
                text_blobs = [t.strip() for t in name_candidates if isinstance(t, str) and t.strip()]
                if not text_blobs:
                    continue
                # Attempt to isolate a name (first non-price token)
                name = ''
                for t in text_blobs:
                    if '£' in t or len(t) < 2:
                        continue
                    name = t
                    break
                if not name:
                    continue
                # Price: look within node
                price_txts = node.xpath(".//*[contains(text(),'£')]/text() | .//text()[contains(.,'£')]")
                price = ''
                for p in price_txts:
                    p = p.strip()
                    if '£' in p and len(p) <= 15:
                        price = p
                        break
                # Description: paragraphs or spans
                desc = ''
                para = node.xpath(".//p[1]")
                if para:
                    desc = para[0].text_content().strip()
                if not desc:
                    # Combine smaller spans
                    spans = node.xpath(".//span/text()")
                    spans = [s.strip() for s in spans if s.strip() and '£' not in s]
                    if spans:
                        desc = ' '.join(spans[:3])
                # Filter out if name duplicates section
                if name.lower() == section.lower():
                    continue
                items.append({
                    'rest_name': REST_NAME,
                    'collection_date': date.today().strftime('%b-%d-%Y'),
                    'menu_section': section,
                    'item_name': name,
                    'item_description': desc,
                    **({'price': price} if price else {})
                })
        except Exception:
            continue
    return items


def parse_jsonld_menus(page_source: str) -> List[Dict]:
    """Parse schema.org Menu data from JSON-LD script tags with full recursive traversal.
    Adds support for nested hasMenuSection trees. Provides menu_section (top level)
    and menu_sub_section (concatenated nested path beyond top-level, if any).
    """
    items: List[Dict] = []
    try:
        tree = html.fromstring(page_source)
        scripts = tree.xpath("//script[@type='application/ld+json']/text()")
        seen_keys: set[Tuple[str, str, str, str]] = set()

        def normalize_price(val: str | float | int | None) -> str:
            if val is None:
                return ''
            try:
                s = str(val).strip()
                if not s:
                    return ''
                if s.startswith('£'):
                    return s
                float(s)
                return f"£{s}"
            except Exception:
                return str(val)

        def clean_desc(desc: str) -> str:
            if not desc:
                return ''
            return desc.replace('<br>', ' ').replace('<br/>', ' ').replace('<br />', ' ').strip()

        def iter_menu_items(menu_name: str, top_section: str, sub_path: List[str], menu_item_obj: dict):
            if not isinstance(menu_item_obj, dict) or menu_item_obj.get('@type') != 'MenuItem':
                return
            name = (menu_item_obj.get('name') or '').strip()
            if not name:
                return
            desc = clean_desc(menu_item_obj.get('description') or '')
            offers = menu_item_obj.get('offers') or {}
            if isinstance(offers, list):
                offers = offers[0] if offers else {}
            price = normalize_price((offers or {}).get('price'))
            nutr = menu_item_obj.get('nutrition') or {}
            suitability = menu_item_obj.get('suitableForDiet') or []
            if isinstance(suitability, str):
                suitability = [suitability]
            sub_section = ' > '.join(sub_path) if sub_path else ''
            key = (name, top_section, sub_section, price)
            if key in seen_keys:
                return
            seen_keys.add(key)
            rec: Dict = {
                'rest_name': REST_NAME,
                'collection_date': date.today().strftime('%b-%d-%Y'),
                'menu_name': menu_name,
                'menu_section': top_section,
                'item_name': name,
                'item_description': desc,
            }
            if sub_section:
                rec['menu_sub_section'] = sub_section
            if price:
                rec['price'] = price
            if isinstance(nutr, dict):
                for k, v in nutr.items():
                    if v is None or v == '':
                        continue
                    rec[f'nutrition_{k}'] = str(v)
            if suitability:
                rec['suitable_for_diet'] = suitability
            items.append(rec)

        def traverse_section(menu_name: str, section_obj: dict, top_section_name: str | None = None, ancestor_path: List[str] | None = None):
            if not isinstance(section_obj, dict) or section_obj.get('@type') != 'MenuSection':
                return
            name = (section_obj.get('name') or '').strip()
            if not name:
                return
            # Determine top-level section and path
            if top_section_name is None:
                top_section_name = name
                path_for_children: List[str] = []
            else:
                path_for_children = (ancestor_path or []) + [name]

            # hasMenuItem can be dict or list
            menu_items = section_obj.get('hasMenuItem')
            if isinstance(menu_items, dict):
                iter_menu_items(menu_name, top_section_name, path_for_children, menu_items)
            elif isinstance(menu_items, list):
                for mi in menu_items:
                    iter_menu_items(menu_name, top_section_name, path_for_children, mi)

            # Recurse into nested sections (hasMenuSection), may be dict or list
            nested = section_obj.get('hasMenuSection')
            if isinstance(nested, dict):
                traverse_section(menu_name, nested, top_section_name, path_for_children)
            elif isinstance(nested, list):
                for ns in nested:
                    traverse_section(menu_name, ns, top_section_name, path_for_children)

        def add_items_from_menu(menu_obj: dict):
            menu_name = (menu_obj.get('name') or '').strip()
            sections = menu_obj.get('hasMenuSection') or []
            if isinstance(sections, dict):
                traverse_section(menu_name, sections)
            else:
                for sec in sections:
                    traverse_section(menu_name, sec)

        for raw in scripts:
            raw = (raw or '').strip()
            if not raw:
                continue
            try:
                data = json.loads(raw)
            except Exception:
                try:
                    fixed = raw.replace('\n', ' ').replace('\t', ' ').strip()
                    data = json.loads(fixed)
                except Exception:
                    continue

            candidates: List[dict] = []
            if isinstance(data, dict):
                if data.get('@type') == 'Menu' and data.get('hasMenuSection'):
                    candidates.append(data)
                graph = data.get('@graph')
                if isinstance(graph, list):
                    for g in graph:
                        if isinstance(g, dict) and g.get('@type') == 'Menu' and g.get('hasMenuSection'):
                            candidates.append(g)
            elif isinstance(data, list):
                for el in data:
                    if isinstance(el, dict) and el.get('@type') == 'Menu' and el.get('hasMenuSection'):
                        candidates.append(el)
            for m in candidates:
                try:
                    add_items_from_menu(m)
                except Exception:
                    continue
    except Exception:
        pass
    return items


def extract_nuxt_state_items(driver) -> List[Dict]:
    """Attempt to extract items from Nuxt state objects (window.__NUXT__).
    This is heuristic: traverse JSON-like structures for dicts with name + (price|offers|nutrition).
    """
    try:
        nuxt_state = driver.execute_script("return window.__NUXT__ || window.$nuxt?.$root?.$options || null;")
    except Exception:
        nuxt_state = None
    if not nuxt_state:
        return []
    items: List[Dict] = []
    seen = set()

    def walk(obj, path: List[str]):
        # Limit traversal depth
        if len(path) > 12:
            return
        if isinstance(obj, dict):
            # Candidate item dict
            name = obj.get('name') if isinstance(obj.get('name'), str) else None
            price = ''
            offers = obj.get('offers')
            if isinstance(offers, dict):
                p = offers.get('price')
                if p is not None:
                    price = str(p)
            elif 'price' in obj and isinstance(obj['price'], (str, int, float)):
                price = str(obj['price'])
            nutrients = obj.get('nutrition') if isinstance(obj.get('nutrition'), dict) else None
            if name and (price or nutrients):
                key = (name, price)
                if key not in seen:
                    seen.add(key)
                    rec = {
                        'rest_name': REST_NAME,
                        'collection_date': date.today().strftime('%b-%d-%Y'),
                        'item_name': name,
                    }
                    if price:
                        if not price.startswith('£'):
                            # attempt numeric
                            try:
                                float(price)
                                price = f"£{price}"
                            except Exception:
                                pass
                        rec['price'] = price
                    if nutrients:
                        for k, v in nutrients.items():
                            if v is None or v == '':
                                continue
                            rec[f'nuxt_nutrition_{k}'] = v
                    # Attempt to infer section from path segments
                    section_guess = next((seg for seg in path if isinstance(seg, str) and seg.isupper() and len(seg) < 40), None)
                    if section_guess:
                        rec['menu_section_guess'] = section_guess
                    items.append(rec)
            for k, v in obj.items():
                walk(v, path + [k])
        elif isinstance(obj, list):
            for i, el in enumerate(obj):
                walk(el, path + [str(i)])

    try:
        walk(nuxt_state, [])
    except Exception:
        return []
    return items


def scan_resource_json(driver) -> List[Dict]:
    """Scan performance resource entries for JSON endpoints and attempt to parse menu-like data."""
    try:
        resource_urls = driver.execute_script("return performance.getEntriesByType('resource').map(r=>r.name);") or []
    except Exception:
        return []
    candidates = []
    for u in resource_urls:
        if any(token in u.lower() for token in ['menu', 'menus', 'tenkites', 'json']):
            if u.endswith('.js'):
                continue
            candidates.append(u)
    items: List[Dict] = []
    headers = {'User-Agent': 'Mozilla/5.0'}
    for url in candidates[:25]:  # safety cap
        try:
            r = requests.get(url, timeout=10, headers=headers)
            if 'application/json' not in r.headers.get('Content-Type','') and not url.lower().endswith('.json'):
                # Heuristic: maybe JSON anyway
                if not r.text.strip().startswith('{') and not r.text.strip().startswith('['):
                    continue
            data = r.json()
        except Exception:
            continue
        # Traverse JSON for MenuItem-like objects
        def walk(obj):
            if isinstance(obj, dict):
                if obj.get('@type') == 'MenuItem' and obj.get('name'):
                    name = obj.get('name').strip()
                    offers = obj.get('offers') or {}
                    if isinstance(offers, list):
                        offers = offers[0] if offers else {}
                    price = offers.get('price') if isinstance(offers, dict) else ''
                    price_str = ''
                    if price:
                        price_str = f"£{price}" if not str(price).startswith('£') else str(price)
                    rec = {
                        'rest_name': REST_NAME,
                        'collection_date': date.today().strftime('%b-%d-%Y'),
                        'item_name': name,
                    }
                    if price_str:
                        rec['price'] = price_str
                    items.append(rec)
                else:
                    for v in obj.values():
                        walk(v)
            elif isinstance(obj, list):
                for el in obj:
                    walk(el)
        walk(data)
    return items


def try_expand_controls(driver):
    """Try to expand sections like accordions or 'show more' buttons to reveal items."""
    keywords = ['show more', 'view more', 'expand', 'see more', 'load more', '+']
    buttons = driver.find_elements(By.XPATH, "//button|//a")
    clicked = 0
    for b in buttons:
        txt = (b.text or '').strip().lower()
        if any(k in txt for k in keywords):
            try:
                driver.execute_script("arguments[0].click();", b)
                time.sleep(0.2)
                clicked += 1
            except Exception:
                continue
    if clicked:
        log(f"Clicked {clicked} expand control(s)")


def expand_all_sections(driver, max_rounds: int = 4):
    """Attempt to expand accordion / collapsible sections to reveal full item lists.
    Strategy:
      - Click any element with aria-expanded='false' and role='button' or a button with plus icon.
      - Repeat until no further changes or max_rounds reached.
    """
    for round_idx in range(max_rounds):
        # Collect potential toggles each round (DOM mutates)
        toggles = driver.find_elements(
            By.XPATH,
            "//button[@aria-expanded='false'] | //div[@role='button' and @aria-expanded='false'] | //button[contains(@class,'accordion') and not(@aria-expanded='true')] | //button[contains(@class,'collapse') and not(@aria-expanded='true')]"
        )
        if not toggles:
            # Also look for headers that might toggle on click (heuristic: contain + sign)
            plus_headers = driver.find_elements(By.XPATH, "//h2|//h3|//h4")
            for h in plus_headers:
                try:
                    txt = (h.text or '').strip()
                    if '+' in txt or txt.lower().endswith('more'):
                        driver.execute_script("arguments[0].click();", h)
                except Exception:
                    continue
            break
        clicked_this_round = 0
        for t in toggles:
            try:
                driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", t)
                time.sleep(0.05)
                driver.execute_script("arguments[0].click();", t)
                clicked_this_round += 1
                time.sleep(0.15)
            except (StaleElementReferenceException, ElementClickInterceptedException, NoSuchElementException):
                continue
            except Exception:
                continue
        if clicked_this_round == 0:
            break
        log(f"Expanded {clicked_this_round} section toggle(s) [round {round_idx+1}]")
        time.sleep(0.2)


def discover_menu_tabs(driver) -> list:
    """Return clickable elements that look like menu category tabs (e.g., A LA CARTE, DESSERTS, DRINKS)."""
    labels = ['carte', 'dessert', 'drink', 'wine', 'kids', 'lunch', 'breakfast']
    tabs = []
    # role=tab or contains typical tab classes
    candidates = driver.find_elements(By.XPATH, "//button[@role='tab'] | //a[@role='tab'] | //li[@role='tab'] | //button[contains(@class,'tab')] | //a[contains(@class,'tab')] | //div[contains(@class,'tab')]/button | //nav//a | //nav//button")
    seen = set()
    for el in candidates:
        try:
            txt = (el.text or '').strip()
            low = txt.lower()
            if len(txt) < 2:
                continue
            if any(lab in low for lab in labels) or 'menu' in low:
                if (txt, low) not in seen:
                    seen.add((txt, low))
                    tabs.append(el)
        except Exception:
            continue
    # Also gather explicit matches by text
    for label in ['A LA CARTE', 'DESSERT', 'DRINK', 'WINE', 'KIDS', 'LUNCH', 'BREAKFAST']:
        try:
            specific = driver.find_elements(By.XPATH, f"//button[contains(translate(., '{label.upper()}', '{label.lower()}'), '{label.lower()}')] | //a[contains(translate(., '{label.upper()}', '{label.lower()}'), '{label.lower()}')]")
            for el in specific:
                if el not in tabs:
                    tabs.append(el)
        except Exception:
            continue
    return tabs


def parse_current_view(driver) -> List[Dict]:
    """Parse both JSON-LD and DOM from current rendered view after any tab/section interactions."""
    src = driver.page_source
    collected = parse_jsonld_menus(src)
    if not collected:
        dom_items = parse_page_source(src)
        collected.extend(dom_items)
    # Additional section-based DOM pass that may reveal missing starters/mains
    sec_items = parse_dom_sections(src)
    if sec_items:
        # Merge but rely on dedupe later
        collected.extend(sec_items)
    return collected


def discover_category_triggers(driver) -> list:
    """Find clickable triggers that likely open category popovers or switch content; more aggressive than tab discovery."""
    keywords = ['starter', 'main', 'dessert', 'drink', 'wine', 'cocktail', 'kids', 'lunch', 'breakfast', 'pudding', 'salad', 'side']
    xpath = "//button|//a|//div[@role='button']"
    candidates = driver.find_elements(By.XPATH, xpath)
    triggers = []
    seen_txt = set()
    for el in candidates:
        try:
            txt = (el.text or '').strip()
            low = txt.lower()
            if not txt or len(txt) > 40:
                continue
            if any(k in low for k in keywords):
                # Exclude previously captured tabs to avoid duplication
                if txt not in seen_txt:
                    seen_txt.add(txt)
                    triggers.append(el)
        except Exception:
            continue
    return triggers


def click_category_triggers_and_capture(driver, items: List[Dict], debug_dir: str):
    """Iterate over discovered category triggers (broader than tabs) to capture additional items.
    Saves HTML snapshot for each view for offline inspection.
    """
    triggers = discover_category_triggers(driver)
    if triggers:
        log(f"Discovered {len(triggers)} category trigger(s); clicking for deeper capture")
    visited_labels = set()
    for idx, trig in enumerate(triggers):
        try:
            label = (trig.text or f'trigger_{idx}').strip()
            if label in visited_labels:
                continue
            visited_labels.add(label)
            driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", trig)
            time.sleep(0.05)
            driver.execute_script("arguments[0].click();", trig)
            time.sleep(0.6)  # allow popover/content swap
            lazy_scroll(driver, steps=3, pause=0.25)
            expand_all_sections(driver)
            try_expand_controls(driver)
            view_items = parse_current_view(driver)
            # Annotate view context
            for vi in view_items:
                if 'view_context' not in vi:
                    vi['view_context'] = label
            before = len(items)
            items.extend(view_items)
            items[:] = dedupe_items(items)
            log(f"Category '{label}': added {len(items)-before} new item(s)")
            # Save debug HTML of this view
            try:
                snap_path = os.path.join(debug_dir, f"view_{idx+1}_{label.replace(' ','_')}.html")
                with open(snap_path, 'w') as f:
                    f.write(driver.page_source)
            except Exception:
                pass
        except Exception:
            continue


def dedupe_items(items: List[Dict]) -> List[Dict]:
    seen = set()
    out = []
    for it in items:
        key = (
            it.get('item_name','').strip(),
            it.get('menu_section','').strip(),
            it.get('price','')
        )
        if key in seen:
            continue
        seen.add(key)
        out.append(it)
    return out


def lazy_scroll(driver, steps: int = 8, pause: float = 0.4):
    last_h = 0
    for _ in range(steps):
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        time.sleep(pause)
        h = driver.execute_script("return document.body.scrollHeight;")
        if h == last_h:
            break
        last_h = h


def save_outputs(records: List[Dict]):
    df = pd.DataFrame(records)
    df.to_csv(file_csv, index=False)
    with open(file_json, 'w') as f:
        import json as _json
        _json.dump(records, f, indent=2)
    with open(file_jsonl, 'w') as f:
        import json as _json
        for rec in records:
            f.write(_json.dumps(rec) + "\n")
    log(f"Scraped {len(records)} item(s)")
    log(f"Saved: {file_csv}")
    log(f"Saved: {file_json}")
    log(f"Saved: {file_jsonl}")


def make_absolute(href: str) -> str:
    if not href:
        return ''
    href = href.strip()
    if href.startswith('http://') or href.startswith('https://'):
        return href
    if not href.startswith('/'):
        href = '/' + href
    return BASE_DOMAIN + href


def extract_menu_links(page_source: str) -> List[str]:
    tree = html.fromstring(page_source)
    hrefs = tree.xpath("//a[contains(@href,'/menu')]/@href")
    cleaned = []
    seen = set()
    for h in hrefs:
        if not h or h.startswith('#'):
            continue
        url = make_absolute(h)
        if url not in seen:
            seen.add(url)
            cleaned.append(url)
    return cleaned


def main():
    log(f"Landing URL: {LANDING_URL}")
    driver = setup_driver()
    items: List[Dict] = []
    try:
        driver.get(LANDING_URL)
        time.sleep(1.5)
        accept_cookies(driver)
        navigate_to_menu_if_present(driver)
        lazy_scroll(driver)
        try_expand_controls(driver)

        # First pass: parse JSON-LD (preferred) then DOM as fallback
        src = driver.page_source
        parsed_ld = parse_jsonld_menus(src)
        log(f"JSON-LD: {len(parsed_ld)} item(s) from landing/menu page")
        items.extend(parsed_ld)
        if len(parsed_ld) == 0:
            parsed_dom = parse_page_source(src)
            log(f"DOM parse: {len(parsed_dom)} item(s) from landing/menu page")
            items.extend(parsed_dom)

        # Attempt to expand all accordions / collapsed sections before tab cycling
        expand_all_sections(driver)
        try_expand_controls(driver)
        time.sleep(0.2)
        # Re-parse after expansions for additional items only (avoid duplicates)
        expanded_pass = parse_current_view(driver)
        if expanded_pass:
            before = len(items)
            items.extend(expanded_pass)
            items = dedupe_items(items)
            log(f"Post-expansion parse added {len(items)-before} new item(s)")

        # If too few items, try navigating to the global /menu page
        if len(items) == 0:
            try:
                driver.get('https://www.caferouge.com/menu')
                time.sleep(1.0)
                accept_cookies(driver)
                lazy_scroll(driver)
                try_expand_controls(driver)
                expand_all_sections(driver)
                src2 = driver.page_source
                parsed2_ld = parse_jsonld_menus(src2)
                log(f"JSON-LD: {len(parsed2_ld)} item(s) from /menu page")
                items.extend(parsed2_ld)
                if len(parsed2_ld) == 0:
                    parsed2_dom = parse_page_source(src2)
                    log(f"DOM parse: {len(parsed2_dom)} item(s) from /menu page")
                    items.extend(parsed2_dom)
            except Exception:
                pass

        # Cycle through discovered menu tabs (e.g., A LA CARTE, DESSERTS, DRINKS) to capture all categories
        tabs = discover_menu_tabs(driver)
        if tabs:
            log(f"Discovered {len(tabs)} candidate menu tab(s); cycling through them")
        visited_tab_texts = set()
        for idx, tab in enumerate(tabs):
            try:
                txt = (tab.text or '').strip()
                if txt and txt in visited_tab_texts:
                    continue
                driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", tab)
                time.sleep(0.05)
                driver.execute_script("arguments[0].click();", tab)
                time.sleep(0.5)  # allow content swap
                lazy_scroll(driver, steps=4, pause=0.25)
                expand_all_sections(driver)
                try_expand_controls(driver)
                tab_items = parse_current_view(driver)
                before = len(items)
                items.extend(tab_items)
                items = dedupe_items(items)
                if txt:
                    visited_tab_texts.add(txt)
                log(f"Tab {idx+1}/{len(tabs)} '{txt}': added {len(items)-before} new item(s)")
            except Exception:
                continue

        # Follow discovered menu links and parse each
        links = extract_menu_links(src)
        if 'src2' in locals():
            links += extract_menu_links(src2)
        # Dedupe and limit to avoid loops
        uniq_links = []
        seen_links = set()
        for u in links:
            if u not in seen_links:
                seen_links.add(u)
                uniq_links.append(u)
        if uniq_links:
            log(f"Discovered {len(uniq_links)} menu-related link(s) to crawl")
        for link in uniq_links[:10]:
            try:
                driver.get(link)
                time.sleep(1.0)
                lazy_scroll(driver)
                try_expand_controls(driver)
                expand_all_sections(driver)
                ps = driver.page_source
                parsed_n_ld = parse_jsonld_menus(ps)
                log(f"JSON-LD: {len(parsed_n_ld)} item(s) from {link}")
                items.extend(parsed_n_ld)
                if len(parsed_n_ld) == 0:
                    parsed_n_dom = parse_page_source(ps)
                    log(f"DOM parse: {len(parsed_n_dom)} item(s) from {link}")
                    items.extend(parsed_n_dom)
            except Exception:
                continue

        # Aggressive category trigger clicking (popover / deeper categories)
        debug_dir = os.path.join(path_out, 'debug_views')
        os.makedirs(debug_dir, exist_ok=True)
        click_category_triggers_and_capture(driver, items, debug_dir)

        # Nuxt state mining (window.__NUXT__)
        nuxt_items = extract_nuxt_state_items(driver)
        if nuxt_items:
            before = len(items)
            items.extend(nuxt_items)
            items = dedupe_items(items)
            log(f"Nuxt state contributed {len(items)-before} new item(s)")

        # Performance resource JSON scan
        perf_items = scan_resource_json(driver)
        if perf_items:
            before = len(items)
            items.extend(perf_items)
            items = dedupe_items(items)
            log(f"Performance resource scan contributed {len(items)-before} new item(s)")
    finally:
        try:
            driver.quit()
        except Exception:
            pass

    # Save debug HTML if nothing found
    if len(items) == 0:
        dbg = os.path.join(path_out, 'debug_cafe_rouge_last.html')
        with open(dbg, 'w') as f:
            f.write(src if 'src' in locals() else '')
        log(f"Saved debug HTML: {dbg}")

    # Final dedupe after all collection passes
    items = dedupe_items(items)
    save_outputs(items)


if __name__ == '__main__':
    main()
