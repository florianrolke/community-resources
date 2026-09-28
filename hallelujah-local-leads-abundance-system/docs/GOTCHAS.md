# Gotchas & Lessons Learned

> 40+ production lessons from scraping 40,000+ businesses across 16 clients, 12 markets, and 6+ chamber platforms. Every one of these cost hours to diagnose.

---

## Chamber of Commerce Scraping

### Platform Detection

1. **GrowthZone and ChamberMaster are the SAME platform** — They use identical `gz-*` CSS classes. The only difference is URL patterns: ChamberMaster uses `/list/searchalpha/{letter}`, GrowthZone uses `/directory/FindStartsWith?term={letter}`.

2. **Chambers often have directories on subdomains** — The public directory is NOT on the main website. Check for: `business.opchamber.org`, `greaterkansascitychamberofcommerce-dev.growthzoneapp.com`, `{slug}.chambermaster.com`.

3. **ChamberMaster `/list` endpoints sometimes 404** — Try the actual `.chambermaster.com` subdomain: `{slug}.chambermaster.com/list`.

4. **Atlas chambers are Angular SPAs** — You cannot scrape them with simple HTTP requests. Options: (a) Use Playwright to capture JWT token from Network tab, then call REST API directly. (b) Use Playwright's `page.evaluate()` to extract from DOM. The REST API approach is faster and more reliable.

5. **Atlas API requires `x-tenant` header** — Each Atlas chamber has a tenant ID (e.g., "CaryNCCOC"). Without it, the API returns 401.

6. **Atlas social type IDs**: 101=Facebook, 102=Twitter, 103=LinkedIn, 113=Instagram, 114=YouTube.

### LinkedIn Pollution (CRITICAL)

7. **Chamber websites put their OWN LinkedIn in headers/footers** — The scraper picks these up and attributes them to every member. Detection: suspiciously high LinkedIn hit rate (>80%) for one chamber, all URLs identical.

8. **Real examples of pollution:**
   - CCSNJ: `linkedin.com/company/chamber-of-commerce-southern-new-jersey` in header
   - Monmouth Regional: `linkedin.com/company/mrcc` in footer — polluted 299/356 entries

9. **Fix:** Add the chamber's social patterns to `CHAMBER_SOCIAL_PATTERNS` list. Check chamber's header/footer BEFORE running detail enrichment on a new chamber.

10. **Never delete enrichment entries to force re-scrape** — Null out only the bad LinkedIn field. Other fields (Facebook, contacts, description, emails) were scraped correctly.

### Social Link Filtering

11. **Share buttons look like social links** — Filter URLs containing `shareArticle`, `sharer.php`, `share?url`, `intent/tweet`.

12. **Elementor social icon widgets are chamber-level** — Filter any `<a>` with class `elementor-social-icon`.

13. **Prioritize `gz-social-*` class links** — These are member-specific and always correct. Regular `<a>` tags with social URLs may be the chamber's own.

14. **ChamberMaster referral URLs need decoding** — Social links use `referral.aspx?URL=` redirect. Decode the URL parameter to get the actual social link.

### Multi-Level Directories

15. **Some chambers have 2-3 level navigation** — Main page → categories → subcategories → members. The standard scraper returns 0 members. Use `scrape_deep.py` for these.

16. **ChamberMaster legacy uses `/prod/allcategories`** — Navigate all categories, then each subcategory has inline member data (no detail pages needed).

17. **WordPress 3-level directories** — Follow `h2.title a` links to member pages, then extract data from individual pages.

### Data Safety

18. **NEVER have two scripts write to the same file** — Race condition lost 720 LinkedIn URLs in one incident. Use per-chamber output files (`detail_enrichment/{slug}.json`).

19. **OneDrive conflicts with atomic writes** — `os.replace()` fails when OneDrive is syncing. Use direct `open(path, 'w')` instead. The `lib/safe_io.py` handles this.

20. **Cloudflare blocking** — Some chambers have Cloudflare protection. Try the `.chambermaster.com` subdomain which typically doesn't have it.

---

## BNI Chapter Scraping

21. **BNI regional portals have different HTML** — Each portal (bni-nc.com, bni-mi.com, manhattanbni.com) has slightly different table structures. The scraper needs a portal registry mapping portals to CSS selectors.

22. **Member count validation is essential** — Compare scraped count against the "Member Count: N" header. If they don't match, pagination likely failed.

23. **BNI pages paginate at 50 members** — Always click through Next/page buttons to get all members.

24. **92% LinkedIn hit rate on BNI members** — This is because BNI members are active business networkers who maintain LinkedIn profiles and have consistent name+company pairings.

25. **BNI portal login walls** — Some portals (e.g., bnisoutheast.com) don't expose member lists publicly. You can only get chapter info, not individual members.

---

## Magazine Advertiser Pipeline

26. **Issuu embed URL is different from the share URL** — Use `e.issuu.com/embed.html?d={SLUG}`, NOT `issuu.com/lifestylepubs/docs/{SLUG}`.

27. **Firecrawl v2 screenshot format** — Use `"formats": ["screenshot"]` only. Do NOT pass `"screenshot": {"fullPage": false}` — it causes errors.

28. **Issuu chrome removal is finicky** — The `crop_issuu_chrome()` function uses brightness analysis. Parameters: `dark_thresh=130`, bottom = top + 59% of height. These values were tuned empirically.

29. **Pages 62+ are typically blank** — File size < 55KB = blank page. Claude Haiku correctly returns 0 ads for these, but you can skip them to save API credits.

30. **Dedup requires name normalization** — Lowercase, strip `'`, `-`, `.`, strip trailing "llc", "inc", "corp". Also maintain merge groups for fuzzy matches (e.g., "Haley Epps Realtor" / "Haley Epp Realtor").

---

## Enrichment Engine

31. **Always validate LinkedIn URLs** — Check that person's name tokens appear in the slug. Search APIs frequently return false positives.

32. **Skip aggregator domains** — When finding websites, filter out: linkedin.com, facebook.com, yelp.com, bbb.org, yellowpages.com, mapquest.com, google.com, chambermaster.com, growthzone.com.

33. **Rate limiting is non-negotiable** — 2s between calls, 15s pause every 10 calls. Without this, you'll hit 429s within minutes.

34. **SMTP verification takes ~30 seconds per email** — Reacher makes a real SMTP connection. Budget this into batch processing time.

35. **API key exhaustion is gradual** — Keys return 429 (rate limit) before 432 (quota exceeded). The rotator handles both.

36. **Perplexity is expensive but high-quality** — Use it for deep research, not bulk searches. Exa is better for bulk LinkedIn/website discovery.

---

## Windows Compatibility

37. **ALWAYS run with `python -X utf8`** — Without this, non-ASCII characters crash the script with `UnicodeEncodeError: 'charmap' codec can't encode character`.

38. **ALWAYS call `fix_encoding()` at script start** — This reconfigures stdout/stderr to UTF-8. Both `-X utf8` flag AND `fix_encoding()` are needed.

39. **Use `errors="replace"` not `errors="strict"`** — Some characters still fail even with UTF-8. The "replace" handler substitutes them instead of crashing.

---

## General Patterns

40. **Checkpoint every 5 records** — Saves progress frequently enough to survive interruptions without losing much work.

41. **Per-chamber output files** — Never merge until all chambers are done. This prevents partial data from corrupting the main file.

42. **Graceful Ctrl+C shutdown** — Register SIGINT handler that saves current progress before exiting.

43. **Dedup by company name (lowercased, stripped)** — Many chambers have duplicate entries across letter pages or pagination.

44. **ICP classification should happen at scrape time** — Don't defer it to enrichment. It's free (keyword matching) and lets you prioritize Tier A for enrichment.
