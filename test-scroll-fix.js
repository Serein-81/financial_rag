const fs = require('fs');
const path = require('path');

const filePath = path.join(__dirname, 'rag_frontend', 'src', 'views', 'TaxSubmissionView.vue');

fs.readFile(filePath, 'utf8', (err, data) => {
  if (err) {
    console.error('Error reading file:', err);
    return;
  }

  console.log('Checking TaxSubmissionView.vue for scroll-related issues...\n');

  const checks = [
    {
      name: 'tax-submission-view class',
      pattern: /\.tax-submission-view\s*\{[^}]*\}/,
      description: 'Main container should have proper styles'
    },
    {
      name: 'overflow-y setting',
      pattern: /overflow-y:\s*(auto|scroll)/,
      description: 'Should have overflow-y: auto or scroll'
    },
    {
      name: 'min-height setting',
      pattern: /min-height:\s*\d+/,
      description: 'Should have min-height set'
    },
    {
      name: 'height setting',
      pattern: /height:\s*(100vh|calc)/,
      description: 'Should have height: 100vh or calc'
    },
    {
      name: 'position sticky on header',
      pattern: /\.page-header\s*\{[^}]*position:\s*sticky/,
      description: 'Header should be sticky for better UX'
    }
  ];

  checks.forEach(check => {
    const regex = new RegExp(check.pattern);
    const match = data.match(regex);
    console.log(`✓ ${check.name}: ${match ? 'Found' : 'Missing'}`);
    if (match) {
      console.log(`  → ${check.description}`);
    } else {
      console.log(`  ✗ ${check.description}`);
    }
  });

  console.log('\n--- Extracted .tax-submission-view CSS ---');
  const containerRegex = /\.tax-submission-view\s*\{([\s\S]*?)\n\}/;
  const containerMatch = data.match(containerRegex);
  if (containerMatch) {
    console.log(containerMatch[0]);
  }

  console.log('\n--- Checking main-content CSS ---');
  const mainContentRegex = /\.main-content\s*\{([\s\S]*?)\n\}/;
  const mainContentMatch = data.match(mainContentRegex);
  if (mainContentMatch) {
    console.log(mainContentMatch[0]);
  }

  console.log('\nAnalysis complete!');
});
