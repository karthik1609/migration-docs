import io
import os
import shutil
import subprocess
import textwrap
import urllib.request
import zipfile
from pathlib import Path

import pytest

PLANTUML_JAR_URL = "https://github.com/plantuml/plantuml/releases/latest/download/plantuml.jar"
PLANTUML_STDLIB_URL = "https://github.com/plantuml/plantuml-stdlib/archive/refs/heads/master.zip"
CACHE_DIR = Path(__file__).parent / ".cache"
DIAGRAM_ROOT = Path(__file__).resolve().parents[1] / "diagrams"
PLANTUML_DIAGRAMS = sorted(DIAGRAM_ROOT.rglob("*.puml"))
MERMAID_DIAGRAMS = sorted(DIAGRAM_ROOT.rglob("*.mmd"))
PUPPETEER_CONFIG = Path(__file__).parent / "puppeteer-config.json"


@pytest.fixture(scope="session")
def plantuml_jar() -> Path:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    jar_path = CACHE_DIR / "plantuml.jar"
    if not jar_path.exists():
        with urllib.request.urlopen(PLANTUML_JAR_URL) as response, jar_path.open("wb") as fh:
            fh.write(response.read())
    return jar_path


@pytest.fixture(scope="session")
def plantuml_include_path() -> str:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    stdlib_dir = CACHE_DIR / "plantuml-stdlib"
    target_dir = stdlib_dir / "stdlib"
    if target_dir.exists():
        return str(target_dir)

    with urllib.request.urlopen(PLANTUML_STDLIB_URL) as response:
        archive_data = response.read()
    with zipfile.ZipFile(io.BytesIO(archive_data)) as archive:
        archive.extractall(CACHE_DIR)
    extracted_dirs = [
        path for path in CACHE_DIR.iterdir() if path.is_dir() and path.name.startswith("plantuml-stdlib-")
    ]
    if not extracted_dirs:
        pytest.fail("Unable to locate extracted PlantUML stdlib directory after download.")
    extracted_dir = extracted_dirs[0]
    if stdlib_dir.exists():
        shutil.rmtree(stdlib_dir)
    shutil.move(str(extracted_dir), str(stdlib_dir))
    target_dir = stdlib_dir / "stdlib"
    if not target_dir.exists():
        pytest.fail("Downloaded PlantUML stdlib archive did not contain the expected 'stdlib' directory.")
    return str(target_dir)


@pytest.mark.parametrize(
    "diagram_path",
    PLANTUML_DIAGRAMS,
    ids=lambda p: str(p.relative_to(Path.cwd())),
)
def test_plantuml_diagrams_render(
    diagram_path: Path, plantuml_jar: Path, plantuml_include_path: str
) -> None:
    include_path = os.pathsep.join([plantuml_include_path])
    cmd = [
        "java",
        "-Djava.awt.headless=true",
        f"-Dplantuml.include.path={include_path}",
        "-jar",
        str(plantuml_jar),
        "-tsvg",
        "-pipe",
    ]
    try:
        content = diagram_path.read_text(encoding="utf-8")
    except UnicodeDecodeError as exc:
        pytest.fail(
            textwrap.dedent(
                f"Failed to read diagram {diagram_path}: {exc}\n"
                "Ensure the file is UTF-8 encoded."
            )
        )
    try:
        result = subprocess.run(
            cmd,
            input=content,
            text=True,
            capture_output=True,
            cwd=diagram_path.parent,
            check=False,
        )
    except FileNotFoundError as exc:
        pytest.fail(
            textwrap.dedent(
                "Unable to execute Java runtime to render PlantUML diagrams.\n"
                f"Command: {' '.join(cmd)}\n"
                f"Error: {exc}"
            )
        )
    if result.returncode != 0:
        detail = textwrap.dedent(
            f"PlantUML rendering failed for {diagram_path}\n"
            f"Command: {' '.join(cmd)}\n"
            f"Exit code: {result.returncode}\n"
            f"Stdout:\n{result.stdout}\n"
            f"Stderr:\n{result.stderr}"
        )
        pytest.fail(detail)


@pytest.mark.parametrize(
    "diagram_path",
    MERMAID_DIAGRAMS,
    ids=lambda p: str(p.relative_to(Path.cwd())),
)
def test_mermaid_diagrams_render(diagram_path: Path) -> None:
    output_path = diagram_path.with_suffix(".svg")
    cmd = [
        "npx",
        "--yes",
        "@mermaid-js/mermaid-cli@10.9.0",
        "-i",
        str(diagram_path),
        "-o",
        str(output_path),
        "-p",
        str(PUPPETEER_CONFIG),
        "--quiet",
    ]
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            cwd=diagram_path.parent,
            check=False,
        )
    except FileNotFoundError as exc:
        pytest.fail(
            textwrap.dedent(
                "Unable to execute Mermaid CLI via npx.\n"
                f"Command: {' '.join(cmd)}\n"
                f"Error: {exc}"
            )
        )
    finally:
        if output_path.exists():
            output_path.unlink()
    if result.returncode != 0:
        detail = textwrap.dedent(
            f"Mermaid rendering failed for {diagram_path}\n"
            f"Command: {' '.join(cmd)}\n"
            f"Exit code: {result.returncode}\n"
            f"Stdout:\n{result.stdout}\n"
            f"Stderr:\n{result.stderr}"
        )
        pytest.fail(detail)

