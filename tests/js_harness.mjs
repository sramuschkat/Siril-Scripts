#!/usr/bin/env node
// Tests for the embedded JavaScript of Svenesis-CosmicView3D.py.
//
// Run:  node tests/js_harness.mjs
//
// Extracts the _CAMERA_BOOTSTRAP_JS template from the Python source,
// injects a test config, and runs it against a stubbed DOM + Plotly.
// Each scenario reproduces a bug actually hit during development:
//   * journey near-clip collapse (eye-center separation must stay
//     above Plotly's ~0.35 culling threshold for the whole flight)
//   * journey start must equal the proven Earth-POV configuration
//   * overlay poller must notice camera motion that Plotly reports
//     ONLY through the internal scene._scene.getCamera() (the
//     "scale bar frozen until R" bug)

import {readFileSync} from 'node:fs';
import {fileURLToPath} from 'node:url';
import {dirname, join} from 'node:path';
import vm from 'node:vm';

const HERE = dirname(fileURLToPath(import.meta.url));
const SCRIPT = join(HERE, '..', 'Svenesis-CosmicView3D.py');

let passed = 0, failed = 0;
function check(name, cond, detail = '') {
  if (cond) { passed++; console.log(`  PASS  ${name}`); }
  else { failed++; console.log(`  FAIL  ${name}  ${detail}`); }
}

function extractBootstrap(cfg) {
  const src = readFileSync(SCRIPT, 'utf-8');
  const m = src.match(/_CAMERA_BOOTSTRAP_JS = r"""([\s\S]*?)"""/);
  if (!m) throw new Error('EXTRACTION ANCHOR LOST: _CAMERA_BOOTSTRAP_JS');
  return m[1]
    .replace('__GV3D_CONFIG__', JSON.stringify(cfg))
    .replace(/<\/?script[^>]*>/g, '');
}

// ---- Stubbed environment ------------------------------------------------
function makeEnv({ranges = [-34, 34], liveCameraDrivesOverlay = false} = {}) {
  const state = {
    relayouts: [], rafQueue: [], now: 0,
    liveEye: {x: 1.6, y: 1.6, z: 1.0},
    scaleTexts: [],
  };
  const mkEl = (isLabel) => {
    const el = {style: {}, children: [], title: '',
      appendChild(c) { this.children.push(c); },
      addEventListener() {}};
    let t = '';
    Object.defineProperty(el, 'textContent', {
      get() { return t; },
      set(v) { t = v; if (isLabel) state.scaleTexts.push(v); },
    });
    return el;
  };
  let created = 0;
  const gd = {
    on() {}, getBoundingClientRect: () => ({width: 1200, height: 800}),
    parentElement: mkEl(false), data: [],
    layout: {scene: {camera: {eye: {x: 1.6, y: 1.6, z: 1.0}}}},
    _fullLayout: {scene: {
      xaxis: {range: [...ranges]}, yaxis: {range: [...ranges]},
      zaxis: {range: [...ranges]},
      camera: {eye: {x: 1.6, y: 1.6, z: 1.0}, up: {x: 0, y: 0, z: 1},
               center: {x: 0, y: 0, z: 0}},
    }},
  };
  if (liveCameraDrivesOverlay) {
    gd._fullLayout.scene._scene = {
      getCamera: () => ({eye: {...state.liveEye}, up: {x: 0, y: 0, z: 1},
                         center: {x: 0, y: 0, z: 0}}),
    };
  }
  const sandbox = {
    document: {
      querySelector: () => gd, getElementsByClassName: () => [gd],
      getElementById: () => null, body: mkEl(false), addEventListener() {},
      // The 3rd created element is the scale-bar label (root, rule, label).
      createElement: () => mkEl(++created === 3),
    },
    window: {addEventListener() {}, gv3d: null, console},
    performance: {now: () => state.now},
    requestAnimationFrame: (cb) => { state.rafQueue.push(cb); return 1; },
    cancelAnimationFrame: () => {},
    setTimeout: () => 0, clearTimeout: () => {},
    Plotly: {
      relayout: (g, a) => {
        if (a['scene.camera.eye']) state.relayouts.push(a);
      },
      restyle: () => {},
    },
    console,
  };
  sandbox.globalThis = sandbox;
  return {state, gd, sandbox};
}

function pump(state, n, dtMs = 280) {
  for (let i = 0; i < n; i++) {
    state.now += dtMs;
    const q = state.rafQueue; state.rafQueue = [];
    q.forEach((cb) => cb(state.now));
  }
}

const CFG = {
  photo: [10.0, -14.0, 12.0], mode: 'cosmic', arms: {},
  armFadeFull: 1.6, armFadeZero: 0.5, intro: false, story: '',
  journey: {targetLy: 3.87e7, targetName: 'NGC 3628',
            waypoints: [[400, 'wp1'], [1e6, 'wp2']]},
};

// ---- Scenario 1: journey camera separation ------------------------------
console.log('== journey: separation stays above the near-clip ==');
{
  const {state, sandbox} = makeEnv();
  vm.createContext(sandbox);
  vm.runInContext(extractBootstrap(CFG), sandbox);
  check('gv3d API exposed', !!sandbox.window.gv3d);
  check('journey exposed', typeof sandbox.window.gv3d.journey === 'function');
  sandbox.window.gv3d.journey();
  pump(state, 45);
  const seps = state.relayouts.map((r) => {
    const e = r['scene.camera.eye'], c = r['scene.camera.center'];
    return Math.hypot(e.x - c.x, e.y - c.y, e.z - c.z);
  });
  check('frames animated', seps.length > 20, `frames=${seps.length}`);
  check('separation floor >= 0.40', Math.min(...seps) >= 0.40,
        `min=${Math.min(...seps).toFixed(3)}`);
  const e0 = state.relayouts[0]['scene.camera.eye'];
  check('starts at Earth POV', Math.hypot(e0.x, e0.y, e0.z) < 0.05,
        JSON.stringify(e0));
  const c0 = state.relayouts[0]['scene.camera.center'];
  const cN = state.relayouts[state.relayouts.length - 1]['scene.camera.center'];
  check('center locked on photo',
        c0.x === cN.x && c0.y === cN.y && c0.z === cN.z);
}

// ---- Scenario 2: overlay poller sees the LIVE camera --------------------
console.log('== overlays: refresh from scene._scene camera only ==');
{
  const {state, sandbox} = makeEnv({liveCameraDrivesOverlay: true});
  vm.createContext(sandbox);
  vm.runInContext(extractBootstrap(CFG), sandbox);
  pump(state, 3, 16);
  const before = state.scaleTexts.length;
  // Mouse-wheel zoom: ONLY the live camera moves; the _fullLayout
  // copy stays frozen (the real Plotly gl3d behaviour).
  state.liveEye = {x: 0.5, y: 0.5, z: 0.3};
  pump(state, 3, 16);
  check('scale bar updated from live camera',
        state.scaleTexts.length > before,
        `texts=${JSON.stringify(state.scaleTexts)}`);
}

console.log(`\n${passed} passed, ${failed} failed`);
process.exit(failed ? 1 : 0);
