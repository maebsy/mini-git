"""REPL 과 실행 옵션.

    python main.py                                   # 실제 시각, sha1 hash
    python main.py --hash-mode counter               # 0000001, 0000002 … (예측 가능)
    python main.py --hash-mode random --seed 42      # 난수지만 재현 가능
    python main.py --fake-time "2024-01-15 09:00:00" --time-step 900   # 커밋마다 15분씩 증가

표준 입력이 파일/파이프이면 프롬프트와 명령을 함께 출력해 실행 기록(transcript)을 만든다.
``#`` 으로 시작하는 줄은 주석으로 보고 실행하지 않는다.
"""

import argparse
import sys
from datetime import datetime
from typing import List, Optional, TextIO

from .cli import CommandRunner
from .clock import SteppingClock, SystemClock
from .hashing import HASH_MODES, HashGenerator
from .models import TIMESTAMP_FORMAT
from .repository import Repository

PROMPT = "mini-git> "
BANNER = "Mini Git 1.0 — 'HELP' 로 명령어 목록, 'exit' 또는 'quit' 로 종료"


def build_parser() -> argparse.ArgumentParser:
    """실행 옵션(hash 모드, 시드, 가짜 시계) 파서."""
    parser = argparse.ArgumentParser(prog="mini-git", description="CLI 기반 Mini Git (커밋 그래프 학습용)")
    parser.add_argument("--hash-mode", choices=HASH_MODES, default="sha1",
                        help="커밋 hash 생성 방식 (기본: sha1)")
    parser.add_argument("--seed", type=int, default=None, help="random 모드의 난수 시드 (재현용)")
    parser.add_argument("--fake-time", metavar="'YYYY-MM-DD HH:MM:SS'",
                        help="커밋 시각을 이 시각부터 시작 (데모/테스트 재현용)")
    parser.add_argument("--time-step", type=float, default=60.0,
                        help="--fake-time 사용 시 커밋 간 간격(초), 기본 60")
    return parser


def build_runner(argv: Optional[List[str]] = None) -> CommandRunner:
    """실행 옵션으로 시계·hash 생성기를 골라 저장소와 명령 실행기를 만든다."""
    args = build_parser().parse_args(argv)
    if args.fake_time:
        try:
            start = datetime.strptime(args.fake_time, TIMESTAMP_FORMAT)
        except ValueError:
            raise SystemExit("--fake-time 형식이 올바르지 않습니다: 'YYYY-MM-DD HH:MM:SS'")
        clock = SteppingClock(start, args.time_step)
    else:
        clock = SystemClock()
    repo = Repository(clock=clock, hash_generator=HashGenerator(args.hash_mode, args.seed))
    return CommandRunner(repo)


def run(runner: CommandRunner, stdin: TextIO = sys.stdin, stdout: TextIO = sys.stdout,
        interactive: Optional[bool] = None) -> int:
    """입력 → 실행 → 출력 루프. exit/quit/EOF 로 종료하고 종료 코드를 반환한다."""
    if interactive is None:
        interactive = stdin.isatty()
    if interactive:
        try:
            import readline  # noqa: F401
        except ImportError:
            pass
        print(BANNER, file=stdout)
    while True:
        try:
            if interactive:
                line = input(PROMPT)
            else:
                line = stdin.readline()
                if line == "":
                    break
                line = line.rstrip("\n")
                print(PROMPT + line, file=stdout)
        except (EOFError, KeyboardInterrupt):
            print(file=stdout)
            break
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if stripped.lower() in ("exit", "quit"):
            break
        for out in runner.execute(stripped):
            print(out, file=stdout)
    return 0


def main(argv: Optional[List[str]] = None) -> int:
    """콘솔 진입점. 출력이 파이프로 끊겨도(BrokenPipe) 조용히 종료한다."""
    import os
    runner = build_runner(argv)
    try:
        return run(runner)
    except BrokenPipeError:
        devnull = os.open(os.devnull, os.O_WRONLY)
        os.dup2(devnull, sys.stdout.fileno())
        return 0
