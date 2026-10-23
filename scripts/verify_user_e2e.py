"""Full user-link E2E with real network/model calls and a temporary local API server."""

import argparse
import json
import os
import socket
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from dotenv import load_dotenv
from e2e_api import Session

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--cases", type=Path, default=ROOT / "scripts/user_e2e_cases.json"
    )
    parser.add_argument("--output", type=Path, default=ROOT / "test-results/user-e2e")
    parser.add_argument("--resume", action="store_true")
    parser.add_argument(
        "--regenerate-case",
        action="append",
        default=[],
        help="Import and generate a named case again",
    )
    parser.add_argument(
        "--revise",
        action="store_true",
        help="Also exercise feedback revision and re-export",
    )
    args = parser.parse_args()
    load_dotenv(ROOT / ".env")
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
    base, token = f"http://127.0.0.1:{port}", "isolated-user-e2e-token"
    env = dict(os.environ, DATA_DIR=str(output), APP_TOKEN=token, SERVE_FRONTEND="true")
    # Exercises all export preparation; remote WeChat account side effects stay out of the test.
    env["WECHAT_APP_ID"] = ""
    env["WECHAT_APP_SECRET"] = ""
    report_file = output / "e2e-report.json"
    report = (
        json.loads(report_file.read_text(encoding="utf8"))
        if args.resume and report_file.exists()
        else dict(started_at=time.strftime("%Y-%m-%d %H:%M:%S"), articles=[])
    )

    def save():
        report_file.write_text(
            json.dumps(report, ensure_ascii=False, indent=2), encoding="utf8"
        )

    with (output / "server.log").open("a", encoding="utf8") as log:
        process = subprocess.Popen(
            [
                sys.executable,
                "-m",
                "uvicorn",
                "backend.app:app",
                "--host",
                "127.0.0.1",
                "--port",
                str(port),
            ],
            cwd=ROOT,
            env=env,
            stdout=log,
            stderr=log,
        )
        try:
            api = Session(base, token, output)
            for _ in range(100):
                try:
                    api.call("GET", "/api/health")
                    break
                except Exception:
                    assert process.poll() is None, "E2E 后端未启动"
                    time.sleep(0.1)
            cases = json.loads(args.cases.read_text(encoding="utf-8-sig"))["articles"]
            complete = {
                a["name"]
                for a in report["articles"]
                if a["status"] in {"generated", "passed", "browser_failed"}
                and a["name"] not in args.regenerate_case
            }

            def generate(case):
                session = Session(base, token, output)
                try:
                    return session.generate(case)
                except Exception as exc:
                    return dict(
                        name=case["name"],
                        url=case["url"],
                        status="failed",
                        error=str(exc)[:350],
                    )
                finally:
                    session.close()

            with ThreadPoolExecutor(max_workers=3) as pool:
                jobs = [
                    pool.submit(generate, case)
                    for case in cases
                    if case["name"] not in complete
                ]
                for job in as_completed(jobs):
                    result = job.result()
                    report["articles"] = [
                        a for a in report["articles"] if a["name"] != result["name"]
                    ]
                    report["articles"].append(result)
                    save()
                    print(
                        json.dumps(
                            dict(
                                name=result["name"],
                                status=result["status"],
                                error=result.get("error"),
                                review_score=result.get("review_score"),
                            ),
                            ensure_ascii=False,
                        ),
                        flush=True,
                    )
            from e2e_browser import browser_checks, revised_preview_checks

            for result in report["articles"]:
                if result["status"] not in {"generated", "browser_failed"}:
                    continue
                try:
                    result["browser"] = browser_checks(base, token, api, result, output)
                    result["status"] = "passed"
                except Exception as exc:
                    result.update(status="browser_failed", error=str(exc)[:500])
                save()
                print(
                    json.dumps(
                        dict(
                            name=result["name"],
                            status=result["status"],
                            error=result.get("error"),
                        ),
                        ensure_ascii=False,
                    ),
                    flush=True,
                )
            from e2e_revision import material_checks, revision_checks

            for result in report["articles"]:
                if result["status"] != "passed":
                    continue
                result["materials_verified"] = material_checks(api, result, output)
                if (
                    args.revise
                    and result.get("feedback_revision", {}).get("status") != "passed"
                ):
                    try:
                        result["feedback_revision"] = revision_checks(
                            api, result, output
                        )
                    except Exception as exc:
                        result["feedback_revision"] = dict(
                            status="failed", error=str(exc)[:500]
                        )
                    print(
                        json.dumps(
                            dict(
                                name=result["name"],
                                feedback_revision=result["feedback_revision"]["status"],
                            ),
                            ensure_ascii=False,
                        ),
                        flush=True,
                    )
                if result.get("feedback_revision", {}).get("status") == "passed":
                    result["revised_browser"] = revised_preview_checks(
                        base, token, result, output
                    )
                save()
            api.close()
        finally:
            process.terminate()
            process.wait(timeout=15)
    print("E2E report: " + str(report_file))
    if len(report["articles"]) != len(cases) or any(
        a["status"] != "passed" for a in report["articles"]
    ):
        sys.exit(1)
    if args.revise and any(
        a.get("feedback_revision", {}).get("status") != "passed"
        for a in report["articles"]
    ):
        sys.exit(1)
    report["completed_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
    report["mode"] = dict(
        real_network=True,
        real_model="deepseek",
        isolated_storage=True,
        remote_wechat_credentials=False,
        direct_publication=False,
    )
    save()


if __name__ == "__main__":
    main()
