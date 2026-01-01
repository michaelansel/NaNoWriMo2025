#!/usr/bin/env node
/**
 * Test Path ID Documentation Accuracy
 *
 * Validates that docs/path-id-display.md accurately describes
 * the ending detection mechanism.
 *
 * Usage:
 *   node scripts/test-path-id-docs.js
 */

const fs = require('fs');
const path = require('path');

function testDocumentationAccuracy() {
    console.log('=== Testing Documentation Accuracy ===\n');

    const docsPath = path.join(__dirname, '..', 'docs', 'path-id-display.md');
    const scriptPath = path.join(__dirname, '..', 'scripts', 'generate-path-lookup.py');

    if (!fs.existsSync(docsPath)) {
        console.log('✗ FAIL: docs/path-id-display.md not found\n');
        return false;
    }

    if (!fs.existsSync(scriptPath)) {
        console.log('✗ FAIL: scripts/generate-path-lookup.py not found\n');
        return false;
    }

    const docsContent = fs.readFileSync(docsPath, 'utf-8');
    const scriptContent = fs.readFileSync(scriptPath, 'utf-8');

    let passed = true;

    // Test 1: Documentation should mention JavaScript querySelectorAll for ending detection
    console.log('Test 1: Ending Detection Documentation');
    const endingSection = docsContent.match(/### Ending Detection[\s\S]*?###/);
    if (!endingSection) {
        console.log('✗ FAIL: Could not find "### Ending Detection" section');
        passed = false;
    } else {
        const section = endingSection[0];

        // Should NOT mention "(if: not $hasLinks)"
        if (section.includes('(if: not $hasLinks)')) {
            console.log('✗ FAIL: Documentation incorrectly mentions "(if: not $hasLinks)"');
            console.log('       Ending detection uses JavaScript, not Harlowe conditionals');
            passed = false;
        } else {
            console.log('✓ PASS: Does not mention incorrect Harlowe conditional');
        }

        // Should mention JavaScript ending detection
        if (section.includes('querySelectorAll') || section.includes("querySelectorAll('tw-link')")) {
            console.log('✓ PASS: Correctly documents JavaScript querySelectorAll usage');
        } else {
            console.log('✗ FAIL: Does not mention JavaScript querySelectorAll for ending detection');
            passed = false;
        }
    }
    console.log();

    // Test 2: Script should generate clickable HTML links
    console.log('Test 2: Clickable Path ID Links');

    // Check if the script generates HTML links to clean path files
    // Looking for pattern like: <a href="allpaths-clean/path-{pathId}.txt" target="_blank"...>
    const hasPathLink = scriptContent.includes('allpaths-clean/path-') &&
                       scriptContent.includes('.txt') &&
                       (scriptContent.includes('target="_blank"') || scriptContent.includes("target='_blank'"));

    if (hasPathLink) {
        console.log('✓ PASS: Script generates clickable links to clean path files');
        console.log('       Links open in new tab with target="_blank"');
    } else {
        console.log('✗ FAIL: Script does not generate clickable links to clean path files');
        console.log('       Expected: <a href="allpaths-clean/path-{pathId}.txt" target="_blank">');
        passed = false;
    }
    console.log();

    return passed;
}

// Main
console.log('Path ID Documentation Tests\n');
console.log('=' .repeat(50) + '\n');

const passed = testDocumentationAccuracy();

console.log('=' .repeat(50));
console.log(passed ? '✓ All documentation tests passed!' : '✗ Documentation tests failed');
process.exit(passed ? 0 : 1);
