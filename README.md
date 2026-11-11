# Stream Tools

Windows tools for streaming Fortnite on TikTok LIVE. Viewer gifts trigger chaos on your game.

| Tool | What it does |
|---|---|
| `fortnite_chaos_LAUNCHER.bat` | Opens Fortnite Chaos, and offers any update first |
| `Start Stream.bat` / `End Stream.bat` | Opens and closes your stream apps and tools |
| `Stream Doctor.bat` | Checks your setup before you go live |
| `Game Boost.bat` | Frees up CPU and RAM. It asks before closing anything |
| `Stream Report.bat` | Shows how your last stream ran |
| `Chaos Clips.bat` | Cuts your stream's best moments into vertical clips |

> **Use at your own risk.** Some Fortnite Chaos effects send fake keyboard and mouse input to the game, and
> Fortnite's anti-cheat can't tell why. That could put your Epic account at risk. Screen effects don't send input.

## Setup

No GitHub account needed.

1. Click **Code > Download ZIP** on this page. Unzip it somewhere you'll keep it.
2. Double-click `SETUP.bat`. It installs what's missing, then opens a window where you choose the apps Start Stream
   opens and where your clips and reports go. It's safe to run again: anything already done gets confirmed and skipped,
   and your settings only change if you choose to.
3. Double-click `fortnite_chaos_LAUNCHER.bat`.
4. In TikTok LIVE Studio, add a **Link** source: `http://127.0.0.1:8766/overlay.html`
5. Connect your gifts, one of these two ways:
   - **BetterTok Creator plan (easiest):** see [BetterTok live events](#bettertok-live-events) below.
   - **Any gift tool (BetterTok, TikFinity):** make each gift trigger a webhook, like `http://127.0.0.1:8766/invert`.
     `http://127.0.0.1:8766/random` picks a random effect.

To try every effect without sending gifts, open `http://127.0.0.1:8766/panel.html` while it's running.
**F8 is the panic key:** it turns everything off.

### BetterTok live events

With BetterTok's Creator plan, Fortnite Chaos can get your gifts, follows and chat straight from BetterTok. There are
no webhook actions to set up, and nothing in BetterTok can quietly stop them firing.

1. Go to [bettertok.app](https://bettertok.app/dashboard/creator/developer), open **Developer**, then **Keys**, and
   click **Create a key**. Copy it straight away: BetterTok only shows it once.
2. Run `SETUP.bat`. In **BetterTok live events**, paste the key, check the gifts that should fire a random effect
   (it starts with Heart Me and Sunglasses) and whether follows should too. Click **Save**.
3. Restart Fortnite Chaos. Its window says `BetterTok: connected to your live events`.
4. In BetterTok's **Actions & Events**, turn off any action that sends those gifts to Fortnite Chaos as a
   webhook, or each one fires twice. Your BetterTok alerts and overlays carry on as normal.
5. Optional, so BetterTok's **test follow** works too: it only goes to actions, not the live events. Add a Follow
   action with a webhook to `http://127.0.0.1:8766/follow`.

Each viewer's follow fires once a day, even if they unfollow and follow again, or it arrives from both the live
events and a webhook. While the live events are connected, gift webhooks from BetterTok are ignored, so an old
gift action left switched on can't fire a second effect (the window says so when it happens). Everything Fortnite
Chaos prints is also kept in `Stream Reports\chaos-log-<date>.txt`.

What happens:

- **Gifts** you listed fire one random effect per gift, so a 3x combo fires 3, up to 5 per combo.
- **Follows** fire a random effect too, if you ticked it. They don't count toward the combo meter or top senders.
- **Chat** goes into the chat votes, with nothing else to set up.

If the window says `the API key was rejected`, the key was mistyped or deleted. Make a new one and paste it in again.
Keep the key private, like a password: anyone with it can read your live events.

### config.json

`SETUP.bat` saves your choices here, so you won't normally need to open it. Updates never change it. Don't share it,
because it can hold your Discord token and BetterTok key.

| Setting | What to put |
|---|---|
| `discord_token` | Your Discord bot's token, for the `!jumpscare` command. Optional |
| `discord_channel_id` | The Discord channel it watches. Optional |
| `bettertok_api_key` | Your BetterTok Developer API key, for [BetterTok live events](#bettertok-live-events). Optional |
| `bettertok_gifts` | Gift name to effect, like `{"Heart Me": "random", "Rose": "invert"}` |
| `bettertok_follow` | The effect a follow fires, like `"random"`. Blank means nothing |
| `reports_folder` | Where reports and logs go. Blank uses `Stream Reports` here |
| `clips_folder` | Where clips go. Blank uses `Clips` here |
| `recordings_folders` | Extra folders with your stream recordings, as well as `Videos` |
| `gift_power` | Makes a gift's effects last longer, like `{"Rose": 1, "Galaxy": 3}` |
| `menu_every_minutes` | How often the gift menu shows itself. 0 turns it off |
| `vote_every_minutes` | How often chat votes on an effect. 0 turns it off. Needs BetterTok live events, or chat sent to `/chat` |
| `gift_icons` | Which gift picture shows beside an effect, like `{"random": "rose.png"}` |
| `apps` | The apps `Start Stream.bat` opens and `End Stream.bat` offers to close |
| `start_stream` | Whether `Start Stream.bat` runs Fortnite Chaos and Game Boost |

In paths, use double backslashes: `C:\\Users\\you\\file.lnk`

### Your Fortnite keys

Fortnite Chaos expects WASD, Space to jump, Left Ctrl to crouch, B for emotes and M for the map. If yours are
different, change them under `Your Fortnite binds` near the top of `fortnite_chaos.py`.

Updates replace that file, so you'd need to change them again after each update.

### Your own pictures and sounds

These go in the `assets` folder:

- `jumpscare.png` and `jumpscare.wav` for the jumpscare. Without them it shows "BOO!" with no sound.
- Gift pictures go in `assets\gifts`, like `rose.png`. The banner shows one when its name matches the gift.

## Updates

When Fortnite Chaos opens, it checks for a newer version. If there is one, it asks before installing.
Your `config.json` and your own pictures and sounds are kept, and replaced files are saved in `Old versions`.

To check by hand, run `py -3 updater.py`.

## Effects

Each is a webhook: `http://127.0.0.1:8766/<name>`

- **Controls (these stack):** `invert` `rotate` `jumpswap` `noscope` `invertmouse` `sensitivity`
- **Aim and map:** `lookdown` `lookup` `spin` `mapspam` `emote`
- **Screen:** `blind` `fog` `jumpscare` `flashbang` `fakeban` `bsod` `blink` `lowhp` `creeper`
- **Random:** `random` picks any effect, `chaos` or `wheel`. `wheel` spins for one effect. `chaos` runs two controls
- **Overlay:** `menu` shows or hides the gift menu. `topsender` shows top senders

Add `?seconds=30` to set the length, and `?user=NAME&gift=GIFT` to show who sent it.

Heartbeat sound: [BigSoundBank](https://bigsoundbank.com/heart-beat-s0218.html), CC0.
