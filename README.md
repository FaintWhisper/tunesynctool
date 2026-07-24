# tunesynctool (formerly Navify)

A Python package and CLI* to transfer music between your local/commercial streaming services. Supports track matching.

*Under development

Tunesynctool supports the following services:

- Spotify (official API)
- Spotify public playlists (optional, read-only source)
- Deezer (optional dependency)
- Any Subsonic-like service (Navidrome, Airsonic, etc.)
- YouTube Music

Support for other services will be added in the future.

## Project relationship and maintenance policy

This repository is a community-maintained fork of [WilliamNT/tunesynctool](https://github.com/WilliamNT/tunesynctool). The original repository remains the upstream project and the source of the broader project direction, authorship, and history.

This fork exists to preserve useful matching and playlist-sync improvements and to provide a maintenance bridge for people already relying on them while equivalent changes are evaluated for contribution upstream. It is not presented as a replacement for, or an official continuation of, the upstream project.

The maintenance principles for this fork are:

- Preserve the upstream project's attribution, license, and Git history.
- Prefer focused contributions back to upstream whenever changes are generally useful.
- Keep fork-specific behavior documented and avoid unnecessary divergence.
- Provide compatibility fixes when possible so existing users are not stranded.
- Direct users back to upstream and retire redundant fork-only maintenance once upstream offers equivalent behavior and a reasonable migration path.

Fork-specific matching behavior should still be considered experimental, but
it now defaults to conservative recording-level matching. Candidates are
ranked using base title, credited artists, and duration, while conflicting
remix/live/instrumental/sped-up metadata and excessive duration differences
cause the matcher to abstain. Use preview options where available and verify
results before modifying important playlists.

### Matching policy

Both `transfer` and `sync` accept
`--match-policy [strict|relaxed]`:

- `strict` is the default. It requires compatible recording/version metadata
  and strongly favors matching duration. It rejects conflicting remixes,
  live/acoustic/instrumental versions, sped/slowed recordings, and large
  duration differences.
- `relaxed` is opt-in. It widens the duration allowance only when a
  recognized soft label such as radio, edit, clean, or explicit explains the
  difference. It still rejects the dangerous version families above,
  conflicting named versions, intros, and excessive differences between
  otherwise unlabeled recordings.

For example:

```shell
tunesynctool transfer --from spotify --to subsonic \
  --match-policy strict "<playlist-id>" --preview
```

## Matcher benchmark

The matcher in this fork was compared with
[upstream commit `7035a4f9b2e12021b7f4a088fb8a3ea610675d37`](https://github.com/WilliamNT/tunesynctool/commit/7035a4f9b2e12021b7f4a088fb8a3ea610675d37).
Both implementations received identical source metadata and frozen target
search responses. The replay was read-only and disabled ISRC and MusicBrainz
shortcuts to isolate common text-based matching. Candidate correctness was
reviewed using title, credited artists, album, and duration.

| Aggregate result | This fork | Upstream |
|---|---:|---:|
| Known-present tracks returning a match | 204/217 (94.0%) | 196/217 (90.3%) |
| Known-absent tracks returning a match | 0/149 (0.0%) | 10/149 (6.7%) |
| Correct targets under the strict definition | 50/50 | 25/50 |
| Wrong targets under the strict definition | 0 | 7 |
| False rejections under the strict definition | 0 | 18 |
| Correct targets under the relaxed definition | 51/51 | 25/51 |
| Wrong targets under the relaxed definition | 0 | 7 |
| False rejections under the relaxed definition | 0 | 19 |

Manual review resolved 61 of 75 queued cases, including every returned match
from the known-absent set; unresolved cases were excluded. The review queue
deliberately overrepresents matcher disagreements, and the dataset was used
while improving the matcher. These figures are therefore benchmark-specific,
not independent estimates of general accuracy. An untouched holdout and a
separate ISRC/MusicBrainz-enabled evaluation are still needed.

Raw metadata, playlist and track identifiers, local-library identifiers,
credentials, search traces, and individual adjudications are intentionally
kept outside this repository. The local `benchmarks/` workspace is excluded
through `.gitignore`; only this aggregate methodology and result summary is
published.

## Usage

Install the official upstream release from PyPI:

```shell
pip install tunesynctool
```

The PyPI package is maintained by the upstream project and may not contain this fork's changes. To use the fork-specific version directly from GitHub:

```shell
pip install git+https://github.com/FaintWhisper/tunesynctool.git
```

This base installation supports Spotify, Subsonic-compatible services, and YouTube Music without installing `streamrip` or Pillow.

Deezer support is optional. Install the fork with its `deezer` extra when you need it:

```shell
pip install "tunesynctool[deezer] @ git+https://github.com/FaintWhisper/tunesynctool.git"
```

The current Deezer driver is read-only: it can be used as a source, but not as
the target of `transfer` or `sync`.

Reading public Spotify playlists without Spotify API credentials is also
optional. Install the fork with its `spotify-public` extra:

```shell
pip install "tunesynctool[spotify-public] @ git+https://github.com/FaintWhisper/tunesynctool.git"
```

For an editable development checkout, use `pip install -e .` for the base
package, `pip install -e ".[deezer]"` to include Deezer, or
`pip install -e ".[spotify-public]"` to include public Spotify playlist
access.

This fork requires Python 3.11 or newer. The base package is checked against
Python 3.11 through 3.14. Deezer is checked separately on Python 3.11 through
3.13 because the current `streamrip` release restricts Pillow to versions that
do not provide Python 3.14 wheels. Until that restriction is resolved upstream,
use Python 3.13 or earlier if you need Deezer.

The `spotify-public` CI job is configured for Python 3.11 through 3.14.
However, `spotifyscraper` currently advertises Python 3.10 through 3.13 in
its classifiers, so Python 3.14 compatibility should be considered
best-effort until it is explicitly supported upstream.

### Public Spotify playlists without API credentials

The `spotify-public` provider reads public playlist metadata and tracks
without a Spotify client ID or client secret. Use it only as the source of a
transfer. For example, after configuring the target service:

```shell
tunesynctool transfer --from spotify-public --to subsonic \
  "https://open.spotify.com/playlist/<public-playlist-id>" --preview
```

This provider is intentionally narrow. It does not access private playlists,
write to Spotify, create or modify playlists, search Spotify, or retrieve
ISRCs. Use the regular `spotify` provider with API credentials for those
features. Public endpoint responses can also omit metadata that the official
API supplies. Local-file rows, podcast episodes, and removed or malformed
playlist entries are skipped rather than converted into placeholder tracks.

The CLI rejects `spotify-public` as a `sync` source. SpotifyScraper can return
a partial result if a later pagination request fails, and destructive
reconciliation must not treat that best-effort snapshot as authoritative.
`transfer` remains safe because it creates or adds to a target rather than
removing tracks based on a possibly incomplete source.

Public playlist access is powered by the unofficial
[`spotifyscraper`](https://pypi.org/project/spotifyscraper/) library. Spotify
can change the public endpoints it relies on without notice, so this path can
temporarily stop working even when the official API-backed provider still
works. Use it consistently with Spotify's terms.

Spotify invitation links can contain a `pt` query parameter that acts as an
invitation token. Treat that token as sensitive: do not paste it into logs,
bug reports, benchmark fixtures, or command history. Remove all query
parameters and pass the bare playlist URL or playlist ID instead. The
`spotify-public` provider only reads playlists that are public; an invitation
token does not add private-playlist support.

## Configuration

Configuration options can be loaded from the environment or be manually specified in code. [Check the upstream documentation](https://github.com/WilliamNT/tunesynctool/wiki/Configuration) for more information.

# FAQ

## Is there a way to use tunesynctool from the CLI?
Yes, see the upstream wiki.

## Does this package offer functionality to download or stream music?
**No**, use the official clients for that.

## How does matching work?

Learn more about the original matching design in the [upstream matching documentation](https://github.com/WilliamNT/tunesynctool/wiki/Track-matching).
The fork ranks all retrieved candidates instead of accepting the first
threshold hit. Duration carries 30% of available weighted evidence, while
release year carries only 1%; missing fields are excluded rather than counted
as matches or mismatches. Strong service IDs, ISRCs, and MusicBrainz recording
IDs remain authoritative.
