import { readFileSync } from "node:fs";

const read = path => readFileSync(new URL(`../${path}`, import.meta.url), "utf8");
const packageVersion = JSON.parse(read("package.json")).version;
const releaseVersion = packageVersion.replace(/\.0$/, "");
const checks = [
  ["pyproject.toml", `version = "${packageVersion}"`],
  ["uv.lock", `name = "backyard-bridge"\nversion = "${packageVersion}"`],
  ["package-lock.json", `"version": "${packageVersion}"`],
  ["main.py", `version="${packageVersion}"`],
  ["README.md", `Current release: \`v.${releaseVersion}\``],
  ["CHANGELOG.md", `## v.${releaseVersion}`],
];

for (const [path, marker] of checks) {
  if (!read(path).includes(marker)) {
    throw new Error(`${path} does not contain release version ${packageVersion}`);
  }
}

console.log(`Release metadata is consistent at ${packageVersion}`);
