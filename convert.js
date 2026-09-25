const fs = require('fs');

function convertHtmlToJsx(html) {
    // Basic replacements
    let jsx = html.replace(/class=/g, 'className=');
    jsx = jsx.replace(/for=/g, 'htmlFor=');
    jsx = jsx.replace(/<!--.*?-->/gs, ''); // Remove comments
    jsx = jsx.replace(/style="([^"]*)"/g, (match, p1) => {
        // Simple inline style to object conversion (very basic)
        const styles = p1.split(';').filter(s => s.trim() !== '');
        const obj = {};
        styles.forEach(s => {
            let [key, val] = s.split(':');
            if (!key || !val) return;
            key = key.trim().replace(/-([a-z])/g, (g) => g[1].toUpperCase());
            obj[key] = val.trim();
        });
        return `style={${JSON.stringify(obj)}}`;
    });

    // Close void tags
    const voidTags = ['img', 'input', 'br', 'hr', 'meta', 'link', 'textarea']; // Note textarea isn't void, but in case
    voidTags.forEach(tag => {
        const regex = new RegExp(`<${tag}\\b([^>]*?)(?<!/)>`, 'g');
        if (tag === 'textarea') return; // textarea has closing tags
        jsx = jsx.replace(regex, `<${tag}$1 />`);
    });

    // Replace <path ...></path> which might have issues or closing tags in HTML
    // (Actually SVG is fine in JSX mostly, except stroke-width etc)
    jsx = jsx.replace(/([a-z]+)-([a-z]+)=/gi, (match, p1, p2) => {
        // e.g. stroke-width -> strokeWidth
        // Only do this if it's inside a tag
        if (match.toLowerCase() === 'data-') return match;
        if (match.toLowerCase() === 'aria-') return match;
        return `${p1}${p2[0].toUpperCase()}${p2.slice(1)}=`;
    });
    
    // Specifically fix the SVG 'clip-rule' 'fill-rule' etc
    jsx = jsx.replace(/clip-rule/g, 'clipRule');
    jsx = jsx.replace(/fill-rule/g, 'fillRule');
    jsx = jsx.replace(/stroke-width/g, 'strokeWidth');
    jsx = jsx.replace(/stroke-linecap/g, 'strokeLinecap');
    jsx = jsx.replace(/stroke-linejoin/g, 'strokeLinejoin');

    return jsx;
}

const landingHtml = fs.readFileSync('apps/web/stitch_landing/code.html', 'utf8');
const dashboardHtml = fs.readFileSync('apps/web/stitch_dashboard/code.html', 'utf8');

// Extract bodies
const extractBody = (html) => {
    const bodyMatch = html.match(/<body[^>]*>([\s\S]*?)<\/body>/i);
    return bodyMatch ? bodyMatch[1] : '';
};

let landingBody = convertHtmlToJsx(extractBody(landingHtml));
let dashboardBody = convertHtmlToJsx(extractBody(dashboardHtml));

fs.writeFileSync('apps/web/stitch_landing/LandingRaw.tsx', `export default function LandingRaw() { return (\n<>\n${landingBody}\n</>\n); }`);
fs.writeFileSync('apps/web/stitch_dashboard/DashboardRaw.tsx', `export default function DashboardRaw() { return (\n<>\n${dashboardBody}\n</>\n); }`);
console.log('Done!');
