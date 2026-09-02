#!/usr/bin/env node
/*
 * sync-app.js
 *
 * app.html in the PROJECT ROOT is the single source of truth.
 * This copies it to wherever the platform shell actually loads it from.
 *
 *     node sync-app.js
 *
 * Android does this automatically (the Gradle "syncWebApp" task runs on every
 * build). Windows / iOS / macOS use this script instead, because rewriting the
 * .csproj / .pbxproj build phases by hand is easy to get wrong.
 */
'use strict';

var fs = require('fs');
var path = require('path');

var root = __dirname;
var src = path.join(root, 'app.html');

if (!fs.existsSync(src)) {
  console.error('ERROR: app.html not found in the project root:\n  ' + src);
  process.exit(1);
}

// every known shell location; only folders that exist are touched
var candidates = [
  'temp/app.html',               // Windows publish source linked by .csproj
  'MatixTheMathClub/app.html',     // Windows (WebView2)
  'Matix the Math Club/app.html',  // iOS + macOS (bundle resource)
  'app/src/main/assets/app.html'   // Android (Gradle normally handles this)
];

var copied = 0;

candidates.forEach(function (rel) {
  var dest = path.join(root, rel);
  var dir = path.dirname(dest);
  if (!fs.existsSync(dir)) return;
  if (path.resolve(dest) === path.resolve(src)) return;
  fs.copyFileSync(src, dest);
  console.log('  synced -> ' + rel);
  copied++;
});

if (copied === 0) {
  console.log('Nothing to sync - no shell folder found next to app.html.');
} else {
  var kb = (fs.statSync(src).size / 1024).toFixed(0);
  console.log('\nDone. ' + copied + ' copy updated (' + kb + ' KB each).');
}
