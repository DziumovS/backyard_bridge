import { execFileSync } from "node:child_process";
import { mkdtempSync, readFileSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const root = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const temporaryDirectory = mkdtempSync(join(tmpdir(), "backyard-bridge-build-"));
const javascriptOutput = join(temporaryDirectory, "script.js");
const cssOutput = join(temporaryDirectory, "styles.css");
const htmlOutput = join(temporaryDirectory, "index.html");
const executableSuffix = process.platform === "win32" ? ".cmd" : "";

try {
  execFileSync(
    process.execPath,
    [
      join(root, "node_modules/terser/bin/terser"),
      join(root, "src/static/js/script.dev.js"),
      "--compress",
      "--mangle",
      "--output",
      javascriptOutput
    ],
    { stdio: "inherit" }
  );
  execFileSync(
    join(root, `node_modules/.bin/lightningcss${executableSuffix}`),
    [
      join(root, "src/static/css/styles.dev.css"),
      "--minify",
      "--output-file",
      cssOutput
    ],
    { stdio: "inherit" }
  );
  execFileSync(
    process.execPath,
    [
      join(root, "node_modules/html-minifier-terser/cli.js"),
      join(root, "src/templates/index.dev.html"),
      "--collapse-whitespace",
      "--remove-comments",
      "--output",
      htmlOutput
    ],
    { stdio: "inherit" }
  );

  const assets = [
    [javascriptOutput, join(root, "src/static/js/script.js")],
    [cssOutput, join(root, "src/static/css/styles.css")],
    [htmlOutput, join(root, "src/templates/index.html")]
  ];
  const staleAssets = assets
    .filter(([generated, committed]) => !readFileSync(generated).equals(readFileSync(committed)))
    .map(([, committed]) => committed.replace(`${root}/`, ""));

  if (staleAssets.length) {
    throw new Error(`Production assets are stale: ${staleAssets.join(", ")}. Run npm run build.`);
  }
} finally {
  rmSync(temporaryDirectory, { recursive: true, force: true });
}
