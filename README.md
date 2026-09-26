# Wedding Invitation Website

A single-page wedding invitation built from the printed card. The Excel file is
the source of truth; the site is generated from it.

```
wedding planning/
├── wedding-details.xlsx     <- edit this
├── build_site.py            <- turns the workbook into docs/data.js
├── make_workbook.py         <- recreates the workbook from scratch
├── make_art.py              <- draws the SVG artwork
├── check_art.py             <- checks the SVGs for broken geometry
└── docs/                    <- this is what gets hosted, and what Pages serves
    ├── index.html
    ├── styles.css
    ├── app.js
    ├── data.js              <- generated, do not hand-edit
    └── assets/
        ├── *.svg            <- decoration (mandala, jali, toran, ...)
        ├── favicon.svg
        └── icons/*.svg      <- one line drawing per ritual
```

`wedding-details.xlsx` is deliberately **not** committed. It is your private
copy, and once filled in it will hold real phone numbers, plus an RSVP List sheet
meant for guests' names and replies. It does not need to be published: `docs/`
is the finished site, and `docs/data.js` is tracked, so editing the spreadsheet
and running `build_site.py` still updates the live site on the next push.

## 1. Fill in the details

Open **`wedding-details.xlsx`**. Every gold `-- FILL IN --` cell needs your
answer. These came off the card by machine reading and still need checking:

**Wedding Details sheet** — Groom, Bride, both parents, city, venue name and
address, Google Maps link, contact phone, WhatsApp number, RSVP deadline.

**Wedding Functions sheet** — all 12 functions, their dates and times are filled
in. Confirm each one against the card, then flip **Verified?** from `No` to
`Yes`. The two to look at hardest are `Kalra / Devpuji` on 10 Dec and the two
separate 3:00 PM functions on 11 Dec. Anything in **Note** stays hidden on the
website until you set Verified to `Yes`, so a half-checked row never shows
guests a note you are still unsure about.

Put a venue name in the **Venue** column only for the days that are not at the
main venue, and it renders as a small tag on that row.

**Venues sheet** — one row per venue, with a Maps link for each.

**RSVP List sheet** — optional, and not the same as the web form. Leave it alone
unless you are tracking responses yourself.

The year is not printed on the card, so `2026` is a placeholder. Change it in
one place, `Wedding Year`, and the function dates follow.

## 2. Rebuild the site

```bash
python3 build_site.py
```

It prints how many functions and days it found, and lists anything still
unfilled. Then open or refresh the page.

The same script is safe to run every time you change the spreadsheet. If it
prints `Missing wedding-details.xlsx`, run `python3 make_workbook.py` first.

## 3. Run it locally

```bash
python3 -m http.server 8347 --directory site
```

Then visit http://localhost:8347

A server is needed because the site loads `data.js` as a separate file; opening
`index.html` by double-clicking it will not work.

## 4. What the site does

- Hero with the couple's names, date, venue, and a live countdown to the first
  function
- Tabbed schedule, one tab per day, with a line drawing for each ritual, and the
  running function is highlighted
- A **Rituals** section explaining every function on the card, so a guest who
  does not know the customs knows what they are walking into
- Venue cards with Maps links and a copy-address button
- Download the whole schedule as a `.ics` file, so all 12 functions land in the
  guest's phone calendar
- RSVP form. Responses are saved in the browser and can be sent on WhatsApp
- Share button, which uses the native share sheet on phones

There is no **Edit details** button, and that is deliberate. The page is opened by
guests, so anything on it has to be read-only: an in-page editor would let any
visitor rewrite the names, the venue, or the contact number, and its *Download
JSON* button would hand them a file shaped exactly like `data.js`. For the same
reason `app.js` reads `data.js` directly and ignores anything in
`localStorage`.

To change a detail, edit `wedding-details.xlsx`, run `python3 build_site.py`, and
reload. That is the only path, and it stays on your machine.

## 5. The artwork

Everything visual is original vector art drawn by `make_art.py`, in a Rajasthani
Hindu palette: maroon, marigold and gold, with a Hawa Mahal jali, a toran of
marigolds and mango leaves, a kalash, a mandap, peacocks, and diyas.

```bash
python3 make_art.py    # rewrites the 24 SVGs in docs/assets/
python3 check_art.py   # verifies paths, viewBoxes and framing
```

`check_art.py` should report `0 problem(s)`. It catches the mistakes that are easy
to make when drawing SVG by hand: a path command with the wrong number of
arguments, a curve that escapes its viewBox, an icon that is not centred, and so
on. Run it after any change to `make_art.py`.

Two things worth knowing if you edit the drawings:

- **The ritual icons are stroked with `currentColor`.** They are inlined into
  `data.js` by `build_site.py` rather than loaded with `<img>`, so they inherit
  the maroon theme. As an `<img>`, a `currentColor` icon renders black.
- **An icon's viewBox is fitted to its own drawing.** That is why the numbers are
  odd, like `viewBox="4.97 9.00 54.02 54.02"`. It is deliberate, and it is what
  keeps all twelve icons the same visual weight.

There are no photographs on the page. If you want real pictures, drop files into
`docs/assets/photos/` and add an `<img>` to the hero in `index.html`; the guest
photos slot in above the names.

## 6. Put it online, free

The `docs/` folder is a static site, so any static host works. All three below
are free and take about five minutes.

### Cloudflare Pages (easiest, no card needed)

1. Push this folder to a new GitHub repo.
2. Sign in at dash.cloudflare.com, then **Workers & Pages → Create → Pages**.
3. Connect the GitHub repo. Build command: leave empty. Output directory: `site`.
4. Deploy. You get a `*.pages.dev` address; add a custom domain later if you
   want one.

### Netlify (best drag-and-drop)

1. Sign in at netlify.com.
2. Drag the `site` folder onto the deploys page.
3. The site is live immediately. Later, connect the repo and set the publish
   directory to `site` so re-pushes go live on their own.

### GitHub Pages

```bash
cd site
git init && git add . && git commit -m "wedding invitation"
git branch -M main
git remote add origin https://github.com/<you>/<repo>.git
git push -u origin main
```

Then in the repo, **Settings → Pages**, source **Deploy from a branch**, branch
`main`, folder `/ (root)`. The address becomes
`https://<you>.github.io/<repo>/`.

### A custom name

Worth it for a wedding. On any of the three hosts, **Custom domains** lets you
point a domain you already own. Names like `abhaywedsanjana.com` are widely
available. Budget roughly $10-15 for a `.com` for one year.

## 7. Sharing it

The **Share** button on the page uses WhatsApp, or the native share sheet on a
phone. To put a link in the printed card or a WhatsApp broadcast, just share the
site's address.

## A note on the details

The printed card is written in a decorative script that OCR cannot read
reliably, so names, parents, venue, and address came off the image by eye and
are the values to check most carefully. The 12 function rows came off the
printed table and are more trustworthy, but still worth a look.

## The photographs

The hero, the Baraat card and the flower band use photographs from Wikimedia
Commons, re-encoded small so the page stays quick on a phone. Each one is
reused under a permissive licence (CC0, public domain, CC BY or CC BY-SA) and
is credited in [`docs/assets/photos/CREDITS.md`](docs/assets/photos/CREDITS.md).

To swap them, drop replacements into `docs/assets/photos/` using the same
filenames — `hero.jpg`, `hero-sm.jpg`, `baraat.jpg`, `ritual.jpg` — or re-run
`python3 fetch_photos.py` then `python3 process_photos.py` to fetch and
re-encode a fresh set.
