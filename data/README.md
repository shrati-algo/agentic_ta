# data/

| Subfolder | Contents | Tracked? |
| --------- | -------- | -------- |
| input/    | Drop folder for production image pairs | gitignored (except .gitkeep) |
| reference/ | Reference images / calibration plates | tracked |
| samples/  | Tiny image pairs used in docs/demos | tracked |

## Provenance
- Real production images live in env-var-watched folders (default
  `/tmp/tad/images/{left,right}`) — not in this folder. See `.env.example`.
- This folder exists for parity with the canonical CV-project template
  and for holding committed reference/sample assets.

## File naming
- `<CHASSIS_NO>_{L,R}.jpg` — chassis ID is 5 chars, VIN format
  (no I/O/Q).
