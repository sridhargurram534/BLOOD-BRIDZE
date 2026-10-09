# Blood Bridge — Full Prototype + Motion UI

## Included
- Separate User Login and Hospital Login
- Animated header with Emergency Scan + Become a Donor actions
- Home page keeps the main Blood Bridge sections/cards together; clicking each module opens its own dedicated page/view
- Blood Request page with saved request + recipient alert preview
- Become a Donor page with alert/reminder preferences
- Thalassemia Support page with saved requirements + donor alert preview
- Hospital directory with search and Use this hospital action
- Donation History / reminders
- Donation Camps
- Partner Portal
- Admin view
- Scroll Word Reveal animation
- Smooth Emergency Actions drawer
- 3D Card Flip pathway cards
- LocalStorage persistence plus Flask API integration
- Navigation no longer shows the old "Overview" label; the first navigation button is "Home"
- Profile username button opens a professional profile popover with username, email, account role, and Logout
- Standalone logout button removed; no profile arrow/chevron is used

## Run on Windows
1. Extract the ZIP.
2. Open Command Prompt in the folder that contains `package.json`.
3. Run `npm.cmd install --legacy-peer-deps --include=optional`.
4. Run `npm.cmd run dev`.
5. Open the Vite Local URL shown in the terminal.

Do not open `index.html` directly; this is a Vite React app.

## Motion UI locations
- Scroll Word Reveal: home page after the module cards.
- Smooth Drawer: Emergency actions button in the home page strip.
- Card Flip: Core Pathways section for Blood Request, Become a Donor, and Thalassemia Support.

## Card photo sources
The three Core Pathway cards now use real-world medical photos loaded from Wikimedia Commons:
- Emergency blood request: Blood bag 2020 — CC0
- Become a donor: Blood Donation at Hospital by Drsmith1968 — CC BY-SA 4.0
- Thalassemia support: Blood transfusion B — CC0

The donor photo includes visible attribution in the card UI. The other two are CC0/public-domain dedications.


## Windows Rollup fix
If Vite reports `Cannot find module '@rollup/rollup-win32-x64-msvc'`, delete `node_modules` and `package-lock.json` once, then run `npm.cmd install --legacy-peer-deps --include=optional` again. This project pins Rollup 4.34.9 and includes the Windows x64 native Rollup package explicitly so the Vite build does not depend on npm optional-dependency recovery.
