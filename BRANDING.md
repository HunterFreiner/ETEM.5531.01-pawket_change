# Pawcket Change Branding Guidelines

Status: Sprint 1 draft, pending team and Product Owner approval.

## The name

The business name is **Pawcket Change** (with the "c"). It's a play on "pocket change," and the pun only works with that spelling, so use it everywhere on the website, in the repo, and in marketing.

Tagline: **Honest care, honest pricing.**

## Who the brand talks to

Budget-conscious dog owners like Dez Calloway, a college student who needs reliable care but gets wary when a business starts adding fees. The brand should feel friendly, plain, and trustworthy. It should never look flashy or luxury.

## Logo

The logo is a paw whose main pad is a coin with a cent sign. It says "affordable pet care" without a word.

| File | Use it for |
| --- | --- |
| `pawcket-change-logo-stacked.svg` / `.png` | Hero sections, About Us, social profile images, print |
| `pawcket-change-logo-horizontal.svg` / `.png` | The website header and footer |
| `pawcket-change-icon.svg` / `.png` | Browser tab (favicon), app icons, small spaces |

Rules:

- Use the SVG on the website whenever possible. Use the PNG where SVG isn't supported. All files have transparent backgrounds.
- The logo is designed for light backgrounds (white or cream). It doesn't have a dark-background version yet, so don't place it on dark colors.
- Leave clear space around the logo equal to the height of the cent sign.
- Minimum width: 120 px for the horizontal logo, 24 px for the icon.
- Don't recolor, stretch, rotate, add shadows, or swap the font.

## Colors

| Name | Hex | Use |
| --- | --- | --- |
| Deep teal | `#1E5F63` | Headings, links, primary buttons, the wordmark |
| Coin gold | `#C8963E` | Accents, highlights, secondary buttons |
| Ink teal | `#12383B` | Text on gold, the cent sign |
| Cream | `#FBF6EC` | Page and section backgrounds |
| Charcoal | `#2B2B2B` | Body text |
| White | `#FFFFFF` | Cards and form fields |

Contrast notes, so the site stays readable:

- Deep teal on white is 7.3:1 and on cream is 6.8:1. Good for text and buttons.
- Charcoal on cream is 13.1:1. Good for body text.
- Ink teal on gold is 4.8:1. Use that pairing for gold buttons.
- Gold on white or cream is only about 2.5:1. Use gold for shapes and accents, never for small text.

## Typography

| Role | Font | Weight |
| --- | --- | --- |
| Headings | Fraunces | 700 or 800 |
| Body and UI | Inter | 400 and 500 |

Both are free on Google Fonts. Use these fallbacks so the page still looks right if the fonts fail to load:

```css
--font-heading: "Fraunces", Georgia, "Times New Roman", serif;
--font-body: "Inter", system-ui, -apple-system, "Segoe UI", Arial, sans-serif;
```

Keep body lines under about 75 characters wide, and write headings in sentence case.

## Voice

Plain, friendly, and specific. Say what something costs. Avoid words like "premium," "exclusive," or "upgrade," and never hide a fee. If a price has conditions, say so right next to the price.

## Quick reference for developers

```css
:root {
  --teal: #1E5F63;
  --gold: #C8963E;
  --ink: #12383B;
  --cream: #FBF6EC;
  --charcoal: #2B2B2B;
  --white: #FFFFFF;
}
```