# Put the input pack here (confidential — git-ignored)

Currently here: `I Married a Broken Soldier. He was a Duke/` (50 episodes, Kuku block layout). Run it with
`python -m promo_engine run -i data/input` or `bash scripts/run_full_pack.sh`.


Anything works: a folder of `.txt` files, sub-folders, PDFs, `.docx`, or a `.zip` (zips inside zips are fine).
Episode numbers are read from headers like `EPISODE 12` inside the files, or from file names (`Ep_12.txt`, `S01E12.pdf`, `12.txt`).

```bash
python -m promo_engine parse -i data/input -v 5     # check how it was understood
python -m promo_engine run   -i data/input           # find the promos
```

Nothing in this folder is committed to git, baked into the Docker image, or uploaded to Vercel.
