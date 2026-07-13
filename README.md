# Football Hub

Static football information site for international competitions, national teams,
club football, popular search guides, and World Cup 2026.

Phase 1 focuses on SEO metadata, crawl files, accessibility basics, and a stable
GitHub Pages-ready static structure.

Phase 2 adds a broader static content experience with search, filtering, mobile
navigation, and richer football guide sections.

## Features

- SEO-ready homepage metadata, canonical URL, Open Graph, Twitter Card, sitemap,
  and robots file
- Match Center, Team Finder, Player Spotlight, Football History, Featured
  Competitions, World Cup 2026, and Popular Guides sections
- Static article search and category filtering for football topics
- Static guide search for evergreen explainer content
- Mobile hamburger navigation and tap-friendly controls
- Back-to-top button and subtle scroll reveal interactions
- About, Editorial Policy, Contact, and Privacy Policy content blocks

## Quality checks

Run the static site validation locally with:

```bash
python3 scripts/validate_site.py
```

The check validates HTML basic elements, JSON-LD, internal links, and the XML sitemap. The same command runs on pushes and pull requests targeting `main`.

## Future Roadmap

- Add football data API integrations for fixtures, standings, teams, and player
  information
- Add Google Analytics after the content structure is stable
- Add Google AdSense after policy pages, traffic, and content coverage are ready
- Expand static cards into dedicated article pages for stronger long-tail SEO

## Structure

- `index.html`
- `styles.css`
- `script.js`
- `assets/`
- `.github/workflows/pages.yml`

The site is designed to run on GitHub Pages without npm, Next.js, or any external
build step.
