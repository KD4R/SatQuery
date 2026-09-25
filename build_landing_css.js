const fs = require('fs');
const { execSync } = require('child_process');

const html = fs.readFileSync('apps/web/stitch_landing/code.html', 'utf8');

// The regex needs to handle the trailing semicolon before the script tag
const configMatch = html.match(/tailwind\.config\s*=\s*(\{[\s\S]*?\})\s*;/);

if (!configMatch) {
  console.error("Could not find tailwind config");
  process.exit(1);
}

let configString = configMatch[1];
configString = configString.replace(/(extend:\s*\{)/, `corePlugins: { preflight: false },\n  $1`);

const tailwindConfig = `
/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    "./apps/web/components/landing/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  ...${configString}
};
`;

fs.writeFileSync('tailwind.config.landing.js', tailwindConfig);

const inputCss = `
@tailwind base;
@tailwind components;
@tailwind utilities;

@layer base {
  html, body { margin: 0; padding: 0; }
  main > :first-child { margin-top: 0 !important; }
  main > :last-child { margin-bottom: 0 !important; }
}
::-webkit-scrollbar { display: none; }
`;
fs.writeFileSync('input.css', inputCss);

console.log("Running tailwindcss...");
try {
  execSync('npx tailwindcss -c tailwind.config.landing.js -i input.css -o apps/web/components/landing/landing.css --minify', { stdio: 'inherit' });
  console.log("Tailwind compiled successfully!");
} catch (e) {
  console.error("Tailwind compilation failed", e);
}

const landingPagePath = 'apps/web/components/landing/LandingPage.tsx';
let landingTsx = fs.readFileSync(landingPagePath, 'utf8');
if (!landingTsx.includes('import "./landing.css";')) {
  // It's after the eslint-disable comments, let's just insert at the bottom of the imports
  landingTsx = landingTsx.replace(/import Link from 'next\/link';/, `import Link from 'next/link';\nimport "./landing.css";`);
  fs.writeFileSync(landingPagePath, landingTsx);
}

console.log("Integration complete.");
