# Speak Your Notes

Voice-to-text dictation notepad for support consultants. Plain HTML + Tailwind CSS + vanilla JS, installable as a PWA.

## Run

```bash
npm install          # first time only (Tailwind build + test tooling)
npm run serve        # http://localhost:5173
```

The microphone only works on **HTTPS** or **localhost**. To use it on your phone, host the folder on any HTTPS static host
(GitHub Pages, Netlify, Cloudflare Pages…) and use *Add to Home Screen* / *Install app*.
No build is needed to deploy – `styles.css` is committed. Run `npm run build:css` after editing classes/`src/input.css`.

## Features

- **Start / Stop Dictation** – Web Speech API, continuous, live interim preview, auto-resumes after silence; red pulsing button while listening.
- Dictation is inserted **at the caret** with smart spacing and sentence capitalisation.
  Voice commands: "full stop", "comma", "question mark", "exclamation mark", "new line", "new paragraph".
- **Shortcut tags**: POS1, GRV, Kitchen Printer, Adumo Base, Terminal, Stock Take (templates with caret placed in the first field),
  plus Timestamp, Follow-up, Resolved. Edit the `TAGS` array in `app.js` to change them.
- **Copy** (button turns into "Copied!"), **Clear** (with Undo), **Tidy** (spacing/capitalisation, with Undo).
- Dark/light theme, language picker (EN-ZA default), autosave to the device, offline app shell.
- Shortcuts: `Ctrl/Cmd+Shift+Space` toggle dictation, `Ctrl/Cmd+Shift+C` copy.

## Browser support

Dictation works in Chrome / Edge (desktop + Android) and Safari (iOS 14.5+). Chrome/Edge send audio to a cloud
speech service, so dictation needs an internet connection. Firefox has no SpeechRecognition – typing and tags still work.

## Verify

```bash
npm test             # drives the real UI in Edge/Chrome with a scripted SpeechRecognition; screenshots in tests/screenshots
```

`node tools/make-icons.mjs` regenerates the PNG icons from `icons/icon.svg`.
