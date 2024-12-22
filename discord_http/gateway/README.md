## Disclaimer
Overall, discord.http/gateway is beta-ready.
Things are still changing, so please do not use this library in production.

## How to test
If you want to beta test this without needing to clone the GitHub project,
you can do so by running the following command:

Docs are not built yet, so you will have to build them yourself if you *really* want them.
Otherwise there aren't really much more to say, it simply adds new event listeners and dispatches them.

```bash
pip install git+https://github.com/AlexFlipnote/discord.http.git@feat/gateway
```

## Todo list
- [x] Handling of all gateway intent events
- [x] Prevent `GUILD_CREATE` from being dispatched before `SHARD_READY`
- [x] Ability to set playing status on boot and change later
- [x] Check if bot is allowed to use special intents
- [x] Properly handle all needed cache flags
- [x] Handling of chunking members
- [x] Handling of ratelimits
- [ ] Make sure it's ready for v2 release

