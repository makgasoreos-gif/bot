# Discord Bot (Probot-style) — Python / discord.py

Ένα Discord bot με moderation, welcome/auto-role, leveling (XP), tickets και custom commands, έτοιμο για deployment στο **Railway**.

## Λειτουργίες

- **Moderation**: `/mod kick`, `/mod ban`, `/mod unban`, `/mod mute`, `/mod unmute`, `/mod warn`, `/mod warnings`, `/mod clearwarnings`, `/mod clear`, `/mod setlog`
- **Welcome & Auto-role**: `/welcome setchannel`, `/welcome setleave`, `/welcome setautorole`, `/welcome disable`
- **Leveling/XP**: αυτόματο XP από μηνύματα, `/rank`, `/leaderboard`
- **Tickets**: `/ticket setup` — δημιουργεί panel με κουμπί για άνοιγμα ticket σε private κανάλι
- **Custom commands**: `/cc add`, `/cc remove`, `/cc list` — π.χ. `!rules` να απαντάει με προκαθορισμένο κείμενο
- **Anti-raid protection**: `/antiraid enable/disable/settings/unlock` — ανιχνεύει μαζικά joins και κλειδώνει το server αυτόματα
- **Invite tracker**: `/invites`, `/inviteleaderboard` — ποιος έφερε ποιον στο server
- **Birthday tracker**: `/birthday set/remove/setchannel/list` — αυτόματο μήνυμα γενεθλίων κάθε χρόνο
- **Suggestions/voting**: `/suggest`, `/suggestions setchannel`, `/resolve` — μέλη προτείνουν, το server ψηφίζει με 👍/👎
- **Giveaways**: `/giveaway`, `/giveawayend` — κουμπί συμμετοχής, αυτόματη επιλογή νικητών
- **Reminders**: `/remindme`, `/reminders`, `/cancelreminder` — προσωπικές υπενθυμίσεις
- **Voice activity tracking**: `/voicetime`, `/voiceleaderboard` — χρόνος σε voice channels
- **Scheduled announcements**: `/announce add/remove/list` — επαναλαμβανόμενα μηνύματα σε τακτά διαστήματα
- `/help`, `/ping`
- 🌐 **Web Dashboard** — login με Discord OAuth2, πλήρης διαχείριση χωρίς Discord: ρυθμίσεις, **members (kick/ban/mute/warn)** και **αποστολή μηνύματος τώρα**, όλα μέσα από browser

Η αποθήκευση γίνεται σε **SQLite** (αρχείο `bot_data.db`), οπότε δεν χρειάζεται εξωτερική βάση για να ξεκινήσεις.

## 1. Τοπικό setup (προαιρετικό, για δοκιμή)

```bash
pip install -r requirements.txt
cp .env.example .env
# βάλε το DISCORD_TOKEN σου μέσα στο .env
python bot.py
```

## 2. Discord Developer Portal

1. Πήγαινε στο https://discord.com/developers/applications → το application/bot σου.
2. Στο tab **Bot**, ενεργοποίησε:
   - **Server Members Intent**
   - **Message Content Intent**
   - (Το **Presence Intent** δεν χρειάζεται)
3. Στο tab **OAuth2 → URL Generator**, επίλεξε scopes `bot` + `applications.commands` και permissions: Administrator (ή τουλάχιστον: Manage Roles, Manage Channels, Kick Members, Ban Members, Moderate Members, Manage Messages, Send Messages, Embed Links). Με το link που παράγεται κάνε invite το bot στο server σου.

## 3. Ρύθμιση του Web Dashboard (OAuth2 login)

Το dashboard τρέχει **μέσα στο ίδιο process** με το bot (ίδιο service, ίδια βάση), οπότε δεν χρειάζεται ξεχωριστό deployment.

1. Στο [Discord Developer Portal](https://discord.com/developers/applications) → το application σου → tab **OAuth2 → General**:
   - Αντίγραψε το **Client ID** και το **Client Secret** (Reset Secret αν δεν το έχεις δει ποτέ).
2. Στο ίδιο tab, κάτω στα **Redirects**, πρόσθεσε:
   - Τοπικά: `http://localhost:8000/callback`
   - Στο Railway: `https://<το-domain-σου>.up.railway.app/callback` (το domain φαίνεται στο Railway αφού κάνεις πρώτο deploy, στο Settings → Networking → Generate Domain)
3. Βάλε στα env vars (τοπικά στο `.env`, στο Railway στα Variables):
   - `DISCORD_CLIENT_ID`
   - `DISCORD_CLIENT_SECRET`
   - `DASHBOARD_REDIRECT_URI` = το ακριβές redirect URL από το βήμα 2
   - `SESSION_SECRET` = ένα τυχαίο μεγάλο string (π.χ. `openssl rand -hex 32`)
4. Μπες στο `https://<domain>/` → **Login with Discord** → θα δεις τα server όπου είσαι admin και υπάρχει το bot → πάτα **Διαχείριση**. Εκεί μπορείς να ρυθμίσεις κανάλια/ρόλους/custom commands/announcements, να πας στο **👥 Members** για kick/ban/mute/warn σε συγκεκριμένο μέλος, ή στο **✉️ Αποστολή μηνύματος** για να στείλεις μήνυμα σε οποιοδήποτε κανάλι άμεσα — όλα χωρίς να χρειάζεται να ανοίξεις το Discord.

Αν θες να απενεργοποιήσεις προσωρινά το dashboard και να τρέχει μόνο το bot, βάλε `ENABLE_DASHBOARD=false`.

## 4. Deployment στο Railway

1. Ανέβασε αυτόν τον φάκελο σε ένα GitHub repo (ή χρησιμοποίησε `railway up` από το Railway CLI απευθείας από τον φάκελο).
2. Στο Railway: **New Project → Deploy from GitHub repo** (ή **Empty Project** + `railway up`).
3. Στο tab **Variables** του service, πρόσθεσε:
   - `DISCORD_TOKEN` = το token του bot σου
   - `PREFIX` = `!` (προαιρετικό)
   - `DISCORD_CLIENT_ID`, `DISCORD_CLIENT_SECRET`, `DASHBOARD_REDIRECT_URI`, `SESSION_SECRET` (για το dashboard — βλ. βήμα 3 παραπάνω)

   > **Αν δεις build error για "GitHub artifact attestations" / mise install python**: είναι γνωστό πρόβλημα του Railway build system, όχι του κώδικα. Το repo περιέχει ήδη `mise.toml` που το απενεργοποιεί, αλλά αν ξαναχτυπήσει, πρόσθεσε επιπλέον Variable `MISE_PYTHON_GITHUB_ATTESTATIONS=false` και κάνε Redeploy.
4. Το Railway θα διαβάσει αυτόματα το `requirements.txt` και το `Procfile` (`web: python bot.py`). Επειδή τώρα το bot σερβίρει και το dashboard, βεβαιώσου ότι το service έχει **δημόσιο domain**: Settings → Networking → Generate Domain. Το Railway βάζει αυτόματα το `PORT` env var, το οποίο ήδη διαβάζει ο κώδικας.
5. **Σημαντικό για persistence**: το filesystem του Railway δεν είναι μόνιμο σε κάθε redeploy. Αν θέλεις τα warnings/levels/tickets να επιβιώνουν σε redeploys, πρόσθεσε ένα **Volume** στο service (Settings → Volumes) και mount το π.χ. στο `/data`, μετά όρισε `DB_PATH=/data/bot_data.db` στα Variables.
6. Deploy — στα logs θα δεις `Logged in as ...` όταν συνδεθεί επιτυχώς.

## 5. Δωρεάν custom domain (χωρίς αναβάθμιση σε Railway Hobby)

Το **μόνιμο** free plan του Railway (μετά το 30ήμερο trial με τα $5 credit) **δεν** υποστηρίζει native custom domains — μόνο το `*.up.railway.app`. Για να βάλεις δικό σου domain χωρίς να πληρώσεις Railway, χρησιμοποιείς το **Cloudflare** (δωρεάν) σαν proxy μπροστά από το Railway URL σου. Το μόνο πραγματικό κόστος είναι η αγορά του ίδιου του domain name από κάποιον provider (π.χ. Namecheap, Porkbun — δεν το πουλάει το Railway ή το Cloudflare).

1. **Βρες το Railway domain σου**: service → Settings → Networking → Public Networking → `Generate Domain` (αν δεν το έχεις ήδη). Θα πάρεις κάτι σαν `myproject-production.up.railway.app` — αντίγραψέ το.
2. **Αγόρασε ένα domain** (αν δεν έχεις ήδη) από όποιον provider θες.
3. **Βάλε το domain στο Cloudflare**: δωρεάν λογαριασμός στο cloudflare.com → `Add a Site` → βάλε το domain σου. Θα σου δώσει 2 nameservers· άλλαξέ τα στον provider που αγόρασες το domain (στις ρυθμίσεις DNS/Nameservers εκεί).
4. **Φτιάξε CNAME record** στο Cloudflare (DNS tab → Add record):
   - Type: `CNAME`
   - Name: `@` (ή `dashboard` αν θες υποτομέα, π.χ. `dashboard.tosite.gr`)
   - Target: το Railway domain σου από το βήμα 1
   - Proxy status: **Proxied** (πορτοκαλί σύννεφο — ΟΧΙ "DNS only"). Αυτό είναι το κρίσιμο σημείο που κάνει τη δουλειά δωρεάν.
5. **SSL/TLS mode**: στο Cloudflare, SSL/TLS → Overview → επίλεξε **Full** (όχι Flexible, γιατί το Railway ήδη κάνει HTTPS). Περίμενε 5-10 λεπτά να ενεργοποιηθεί το certificate.
6. **Ενημέρωσε τα env vars**: στο Railway Variables, άλλαξε `DASHBOARD_REDIRECT_URI=https://το-domain-σου/callback`. Στο Discord Developer Portal → OAuth2 → Redirects, πρόσθεσε το ίδιο ακριβές URL. Χωρίς αυτό το login του dashboard θα σπάει.

## Δομή αρχείων

```
discord-bot/
├── bot.py                  # entry point
├── requirements.txt
├── Procfile                 # web: python bot.py
├── runtime.txt
├── mise.toml                 # fixes a Railway build issue installing Python
├── .env.example
├── utils/
│   ├── db.py                 # SQLite schema & helpers
│   └── state.py               # shares the running bot instance with the dashboard
├── dashboard/
│   ├── app.py                 # FastAPI app (OAuth2 login + settings pages)
│   ├── oauth.py                # Discord OAuth2 helper calls
│   └── templates/              # Jinja2 HTML templates
└── cogs/
    ├── moderation.py
    ├── welcome.py
    ├── leveling.py
    ├── tickets.py
    ├── customcommands.py
    ├── antiraid.py
    ├── invites.py
    ├── birthdays.py
    ├── suggestions.py
    ├── giveaways.py
    ├── reminders.py
    ├── voice_activity.py
    ├── announcements.py
    └── general.py             # /help, /ping
```

## Επέκταση

Ο κώδικας είναι χωρισμένος σε **cogs**, οπότε το να προσθέσεις νέες λειτουργίες (π.χ. μουσική, economy, reaction roles, giveaways) είναι απλά να φτιάξεις νέο αρχείο στο `cogs/` με τη μορφή `async def setup(bot)` και να το προσθέσεις στη λίστα `INITIAL_COGS` στο `bot.py`.
