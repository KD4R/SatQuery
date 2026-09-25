const fs = require('fs');

function cleanJsx(filePath) {
    let content = fs.readFileSync(filePath, 'utf8');
    
    // Remove <script>...</script> blocks
    content = content.replace(/<script\b[^<]*(?:(?!<\/script>)<[^<]*)*<\/script>/gi, '');
    
    // Remove <style>...</style> blocks
    content = content.replace(/<style\b[^<]*(?:(?!<\/style>)<[^<]*)*<\/style>/gi, '');

    // Some attributes have invalid JSX names if missed
    content = content.replace(/autocomplete=/gi, 'autoComplete=');
    content = content.replace(/autofocus=/gi, 'autoFocus=');
    content = content.replace(/maxlength=/gi, 'maxLength=');

    fs.writeFileSync(filePath, content);
}

cleanJsx('apps/web/stitch_landing/LandingRaw.tsx');
cleanJsx('apps/web/stitch_dashboard/DashboardRaw.tsx');
console.log('Cleaned');
