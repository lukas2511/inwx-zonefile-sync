# inwx-zonefile-sync

- Create `zones` directory
- Copy or create zone files in the `zones` directory
- Copy `inwx/conf.cfg` to `conf.cfg` and edit `live` section to match your account
- Run `python3 sync.py`
- Done.

Keep in mind that SOA records and NS records on the root of the zone are completely ignored (making it easy to copy over old files),
and that INWXs restrictions are in place (e.g. minimum ttl of 300 seconds).
