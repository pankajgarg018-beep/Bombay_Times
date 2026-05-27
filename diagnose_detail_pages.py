"""
Diagnostic: inspect bt-picks/electronics and intimate-diaries DOM
to identify selectors for 'Top Pick From the Editors This Week'
and 'Tanisha Rao' author section.
"""
from playwright.sync_api import sync_playwright

CHROME = r"C:\Program Files\Google\Chrome\Application\chrome.exe"

def inspect(pg, url, label):
    print(f"\n{'='*70}")
    print(f"PAGE: {label} - {url}")
    print('='*70)
    pg.goto(url, timeout=30000)
    try:
        pg.wait_for_load_state("networkidle", timeout=20000)
    except Exception:
        pass

    # ── Generic: dump all unique section/heading texts ──────────────────────
    texts = pg.evaluate("""
        () => {
            const tags = ['h1','h2','h3','h4','h5','strong','span.title','div.title',
                          '.section-title','.widget-title','.cat-title','p.bold'];
            const seen = new Set();
            const results = [];
            for (const tag of tags) {
                for (const el of document.querySelectorAll(tag)) {
                    const t = el.innerText.trim();
                    if (t && t.length < 120 && !seen.has(t)) {
                        seen.add(t);
                        results.push({tag: el.tagName + (el.className ? '.'+el.className.split(' ')[0] : ''),
                                      text: t});
                    }
                }
            }
            return results.slice(0, 40);
        }
    """)
    print("\n--- Headings / section titles ---")
    for t in texts:
        print(f"  <{t['tag']}> {t['text'][:90]}")

    # ── Selectors for finding "Top Pick" section ─────────────────────────────
    print("\n--- Checking 'Top Pick' section selectors ---")
    top_pick_info = pg.evaluate("""
        () => {
            const phrase = 'Top Pick From the Editors This Week';
            const allEls = [...document.querySelectorAll('*')];
            for (const el of allEls) {
                if (el.innerText && el.innerText.trim() === phrase) {
                    // Found exact match — check parent for article links
                    let container = el;
                    for (let i = 0; i < 6; i++) {
                        const links = container.querySelectorAll('a');
                        const imgLinks = [...links].filter(a => a.querySelector('img') || a.href.includes('/bt-picks/'));
                        if (imgLinks.length > 0) {
                            return {
                                found: true,
                                headingTag: el.tagName,
                                headingClass: el.className,
                                containerTag: container.tagName,
                                containerClass: container.className,
                                firstHref: imgLinks[0].href,
                                depth: i
                            };
                        }
                        container = container.parentElement;
                        if (!container) break;
                    }
                    return { found: true, headingTag: el.tagName, headingClass: el.className, noLinks: true };
                }
            }
            // Partial match
            for (const el of allEls) {
                if (el.innerText && el.innerText.trim().includes('Top Pick') && el.children.length < 3) {
                    return { partial: true, tag: el.tagName, cls: el.className, text: el.innerText.trim().slice(0,80) };
                }
            }
            return { found: false };
        }
    """)
    print(f"  Top Pick result: {top_pick_info}")

    # ── Selectors for "Tanisha Rao" ───────────────────────────────────────────
    print("\n--- Checking 'Tanisha Rao' author section ---")
    tanisha_info = pg.evaluate("""
        () => {
            const allEls = [...document.querySelectorAll('*')];
            const candidates = allEls.filter(el =>
                el.innerText && el.innerText.includes('Tanisha Rao') && el.children.length < 5
            );
            if (!candidates.length) return { found: false };
            const el = candidates[0];
            // Look for article links near this element
            let container = el;
            for (let i = 0; i < 8; i++) {
                const links = [...container.querySelectorAll('a')].filter(a =>
                    a.href.includes('/intimate-diaries/') ||
                    a.querySelector('img') || a.href.includes('bombaytimes')
                );
                if (links.length > 0) {
                    return {
                        found: true,
                        elTag: el.tagName, elClass: el.className,
                        containerTag: container.tagName, containerClass: container.className,
                        firstHref: links[0].href,
                        totalLinks: links.length,
                        depth: i
                    };
                }
                container = container.parentElement;
                if (!container) break;
            }
            return { found: true, elTag: el.tagName, noLinks: true };
        }
    """)
    print(f"  Tanisha Rao result: {tanisha_info}")

    # ── General article link counts ──────────────────────────────────────────
    print("\n--- General article link selectors ---")
    for sel in [
        "ol.sub-cat-ol li a.right-img-a",
        "ol.sub-cat-ol li a",
        "a.right-img-a",
        "a.newsItem",
        "a[class*='href-style']",
        "a[href*='/bt-picks/electronics/']",
        "a[href*='/intimate-diaries/']",
    ]:
        cnt = pg.locator(sel).count()
        if cnt:
            first = pg.locator(sel).first.get_attribute("href") or ""
            print(f"  {sel:<50} => {cnt:3d}  first: {first[:70]}")
        else:
            print(f"  {sel:<50} => {cnt:3d}")


with sync_playwright() as p:
    b = p.chromium.launch(executable_path=CHROME, headless=True)
    pg = b.new_page()

    inspect(pg, "https://www.bombaytimes.com/bt-picks/electronics", "BT-Picks Electronics")
    inspect(pg, "https://www.bombaytimes.com/intimate-diaries", "Intimate Diaries")

    b.close()
    print("\nDone.")
