#!/bin/bash
cd "$(dirname "$0")" || exit 1
exec /usr/bin/env node ./scripts/start-electron.js
