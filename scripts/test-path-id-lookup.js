#!/usr/bin/env node
/**
 * Test Path ID Lookup JavaScript Logic
 *
 * Validates that the JavaScript parsing logic in PathIdLookup.twee
 * correctly handles the history format from Harlowe.
 *
 * Usage:
 *   node scripts/test-path-id-lookup.js
 */

const fs = require('fs');
const path = require('path');

// Test the parsing logic
function testParsingLogic() {
    console.log('=== Testing Path ID Parsing Logic ===\n');
    let passed = 0;
    let failed = 0;

    // Test cases: [historyText, currentPassage, expectedRoute]
    const testCases = [
        // Simple path (2 passages)
        ['Start|||', 'Day 30 KEB', 'Start→Day 30 KEB'],

        // Longer path
        ['Start|||raining|||A rumor|||', 'Day 28 KEB', 'Start→raining→A rumor→Day 28 KEB'],

        // Empty history (first passage)
        ['', 'Start', 'Start'],

        // Path with spaces in names
        ['Start|||Day 1 KEB|||wait for travelers to approach|||', 'Day 23 KEB',
         'Start→Day 1 KEB→wait for travelers to approach→Day 23 KEB'],

        // Trailing delimiter handled correctly
        ['Start|||raining|||', 'Day 19 KEB', 'Start→raining→Day 19 KEB'],
    ];

    for (const [historyText, currentPassage, expected] of testCases) {
        // Parse history (same logic as PathIdLookup.twee)
        const pastPassages = historyText.split('|||').filter(s => s && s.length > 0);
        const fullPath = pastPassages.concat([currentPassage]);
        const route = fullPath.join('→');

        if (route === expected) {
            console.log(`✓ PASS: "${historyText}" + "${currentPassage}"`);
            console.log(`       → ${route}`);
            passed++;
        } else {
            console.log(`✗ FAIL: "${historyText}" + "${currentPassage}"`);
            console.log(`       Expected: ${expected}`);
            console.log(`       Got:      ${route}`);
            failed++;
        }
        console.log();
    }

    console.log(`Results: ${passed} passed, ${failed} failed\n`);
    return failed === 0;
}

// Verify PathIdLookup.twee was generated and contains expected structure
function testGeneratedFile() {
    console.log('=== Checking Generated PathIdLookup.twee ===\n');

    const lookupPath = path.join(__dirname, '..', 'src', 'PathIdLookup.twee');

    if (!fs.existsSync(lookupPath)) {
        console.log('✗ FAIL: src/PathIdLookup.twee not found');
        console.log('  Run ./scripts/build-core.sh first\n');
        return false;
    }

    const content = fs.readFileSync(lookupPath, 'utf-8');

    // Check for required components
    const checks = [
        ['[script] tag', /:: PathIdLookup \[script\]/],
        ['pathIdLookup object', /window\.pathIdLookup\s*=/],
        ['getPathId function', /window\.getPathId\s*=/],
        ['getCurrentPassage function', /function getCurrentPassage\(/],
        ['getFullPath function', /function getFullPath\(/],
        ['MutationObserver setup', /new MutationObserver/],
        ['||| delimiter split', /split\('\|\|\|'\)/],
    ];

    let allPassed = true;
    for (const [name, pattern] of checks) {
        if (pattern.test(content)) {
            console.log(`✓ Contains ${name}`);
        } else {
            console.log(`✗ Missing ${name}`);
            allPassed = false;
        }
    }

    // Count path mappings
    const mappings = content.match(/"[^"]+→[^"]+"/g) || [];
    console.log(`\n  Path mappings: ${mappings.length}`);

    if (mappings.length === 0) {
        console.log('✗ No path mappings found');
        allPassed = false;
    }

    console.log();
    return allPassed;
}

// Verify PathIdDisplay.twee footer structure
function testFooterFile() {
    console.log('=== Checking PathIdDisplay.twee Footer ===\n');

    const footerPath = path.join(__dirname, '..', 'src', 'PathIdDisplay.twee');

    if (!fs.existsSync(footerPath)) {
        console.log('✗ FAIL: src/PathIdDisplay.twee not found\n');
        return false;
    }

    const content = fs.readFileSync(footerPath, 'utf-8');

    const checks = [
        ['[footer] tag', /:: PathIdDisplay \[footer\]/],
        ['history data span', /id="harlowe-history-data"/],
        ['current passage span', /id="harlowe-current-passage"/],
        ['for loop with delimiter', /\(for: each _p.*\|\|\|/],
        ['passage name print', /\(passage:\)'s name/],
    ];

    let allPassed = true;
    for (const [name, pattern] of checks) {
        if (pattern.test(content)) {
            console.log(`✓ Contains ${name}`);
        } else {
            console.log(`✗ Missing ${name}`);
            allPassed = false;
        }
    }

    console.log();
    return allPassed;
}

// Main
console.log('Path ID Display - Validation Tests\n');
console.log('=' .repeat(50) + '\n');

const results = [
    testParsingLogic(),
    testGeneratedFile(),
    testFooterFile(),
];

const allPassed = results.every(r => r);
console.log('=' .repeat(50));
console.log(allPassed ? '✓ All tests passed!' : '✗ Some tests failed');
process.exit(allPassed ? 0 : 1);
