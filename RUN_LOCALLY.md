# Run the RetireSafe backend on your own computer (Anaconda Prompt)

This guide gets the backend running on Windows with Anaconda in about 10 minutes, then shows you
what it does. It also works on macOS and Linux (use a normal terminal; the commands are the same
except where noted).

You need **Anaconda or Miniconda**, an internet connection, and about **1 GB** of free disk space
(most of it is the real traffic log). You do **not** need AWS, Azure or Terraform: the demo uses
real Terraform output that is already in the repository.

---

## 1. Get the code

**Option A: with Git** (if `git --version` works in Anaconda Prompt):

```bat
cd %USERPROFILE%\Documents
git clone https://github.com/BOOMER16/RetireSafe.git
cd RetireSafe
git checkout claude/wonderful-albattani-9aheed
```

**Option B: without Git.** On GitHub, open the repository, switch the branch selector to
`claude/wonderful-albattani-9aheed`, click **Code → Download ZIP**, unzip it (for example to
`Documents\RetireSafe`), then in Anaconda Prompt:

```bat
cd %USERPROFILE%\Documents\RetireSafe
```

Make sure you are in the folder that contains `demo.py` and the `backend` folder (`dir` should list both).

## 2. Create the environment (once)

```bat
conda create -n retiresafe python=3.11 -y
conda activate retiresafe
pip install -e "backend[test]"
```

Check it worked:

```bat
retiresafe --version
```

It should print `retiresafe 0.1.0`.

> Every time you open a new Anaconda Prompt, run `conda activate retiresafe` and `cd` into the
> RetireSafe folder again.

## 3. Download the real traffic data (once, about 37 MB)

```bat
python scripts\get_data.py
```

This downloads the NASA-HTTP July and August 1995 web logs (3.46 million real requests), checks
their SHA-256 fingerprints, and writes `data\nasa-http\nasa_jul_aug_1995.log` (373 MB). You can
skip this step; the demo then runs without traffic evidence and tells you what changes.

## 4. Watch what the system does

```bat
python demo.py --pause
```

`--pause` stops after every step so you can read it; press **Enter** to continue. Without
`--pause` it runs straight through (about one minute). The demo walks through one realistic
case: an organisation wants to delete four S3 buckets after an event.

| Step | What you see |
|---|---|
| 0 | The five conditions a takeover needs |
| 1 | The resources the Terraform plan wants to delete |
| 2 | Whether someone else could register each freed name, with the AWS source quote |
| 3 | Every place each name is still used: DNS records, lines of code, other config, and which ones have an integrity check |
| 4 | Real traffic per bucket: requests, clients, how long it has been quiet, how long it must be quiet |
| 5 | The five-condition check for every reference (yes / NO / ?) and whether that path is hijackable |
| 6 | The verdict per bucket and the gate result (FAIL) |
| 7 | The fixes it proposes (code diff, DNS change batch, Terraform to keep the name) |
| 8 | The fixes applied, and the re-check (PASS) |

Results are saved in the `demo_output` folder. Open `demo_output\before_report.md` in any text
editor (or VS Code) to read the full report.

Try the variations:

```bat
python demo.py --mode balanced
python demo.py --no-traffic
```

* `--mode balanced`: `legacy_downloads` changes from TOMBSTONE to RELEASE, because its real
  traffic has been silent for 16.5 days, longer than the 3.9 days needed. Strict mode (the
  default) never releases a name that someone else could claim.
* `--no-traffic`: without logs, RetireSafe cannot rule out remaining users, so nothing that could
  be claimed is released.

## 5. Use the command-line tool directly

This is how a team would use it in CI. The exit code is **0** if the deletion may proceed and
**2** if it must not:

```bat
retiresafe assess --plan pilot\generated\plan_before.json --dns pilot\generated\route53_before.json --repo app=pilot\app --log data\nasa-http\nasa_jul_aug_1995.log,format=clf,host=rs-pilot-event-assets-2025.s3.amazonaws.com,path_prefix=/images/ --as-of 1995-09-01T03:59:53Z --out my_evidence.json --markdown my_report.md
echo %ERRORLEVEL%
```

(On macOS/Linux use `/` instead of `\` and `echo $?`.)

Other commands:

```bat
retiresafe assess --help
retiresafe sources
retiresafe scan --hosts my_hostnames.txt --out drift.json
```

* `retiresafe sources` prints the source quote behind every rule.
* `retiresafe scan` runs a live, read-only DNS and S3 check of hostnames listed in a text file,
  one per line. **Only scan names your organisation owns.**

## 6. Try the REST API in your browser (no UI needed)

```bat
retiresafe serve
```

Leave that window open and go to **http://127.0.0.1:8080/docs**. FastAPI generates an
interactive page where you can call every endpoint:

1. Open **POST /v1/assessments**, click **Try it out**.
2. `plan`: choose `pilot\generated\plan_before.json`.
3. `dns`: add `pilot\generated\route53_before.json`.
4. `repo`: zip the `pilot\app` folder (right-click → *Send to → Compressed (zipped) folder*) and choose the zip.
5. `config`: `{"as_of": "1995-09-01T03:59:53Z"}`
6. Click **Execute**. You get the full evidence record back. Copy its `assessment_id` into
   **GET /v1/assessments/{aid}/report.md** to read the Markdown report.

Press **Ctrl+C** in the Anaconda Prompt window to stop the server. Assessments are stored in
`retiresafe.db` in the folder you started the server from.

## 7. Run the tests (optional)

```bat
cd backend
python -m pytest -q
cd ..
```

Expect `42 passed` with the traffic data downloaded. Without it, 2 tests are skipped.

---

## Troubleshooting

| Problem | Fix |
|---|---|
| `'retiresafe' is not recognized` | Run `conda activate retiresafe` first, then repeat `pip install -e "backend[test]"` from the RetireSafe folder |
| `pip install` says it cannot find `backend` | You are in the wrong folder: `cd` to the folder that contains `demo.py` |
| `get_data.py` fails with a network or SSL error | Corporate proxies can block GitHub downloads. Try another network, or download the two `.gz` files from https://github.com/greymd/NASA-HTTP into `data\nasa-http\` and run the script again (it verifies them) |
| `checksum mismatch` | The download was corrupted or altered. Delete the files in `data\nasa-http\` and run the script again |
| The demo says the traffic log is missing | Run step 3, or point to it: `python demo.py --log C:\path\to\nasa_jul_aug_1995.log` |
| Port 8080 is already in use | `retiresafe serve --port 8090`, then open http://127.0.0.1:8090/docs |
| `/docs` page is blank | It loads its page styling from the internet (cdn.jsdelivr.net); check your connection |
| Odd characters in the console | Harmless; the demo only prints plain text. Run `chcp 65001` first if you want UTF-8 |

## What is real in the demo

* **Terraform plans and DNS exports:** real output from Terraform 1.16.4 and the official AWS
  provider 6.67.0, run against a local AWS emulator (moto).
* **Traffic:** the real NASA-HTTP 1995 logs, unmodified.
* **Invented:** the organisation, the bucket names and the small app in `pilot\app`. They use the
  reserved `.example` domain, so they cannot point at anything real.

See `pilot/README.md` for details.
