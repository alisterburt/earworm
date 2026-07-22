// "Jungle" delay-line pitch shifter (after Chris Wilson's classic Web Audio demo).
// Two crossfading, sawtooth-modulated delay lines shift pitch in real time without
// changing tempo. It's cheap and has audible warble/artifacts — which is the point.
const delayTime = 0.100, fadeTime = 0.050, bufferTime = 0.100;

function createFadeBuffer(ctx, activeTime, fadeTime) {
  const len1 = activeTime * ctx.sampleRate, len2 = (activeTime - 2 * fadeTime) * ctx.sampleRate;
  const length = len1 + len2, buf = ctx.createBuffer(1, length, ctx.sampleRate), p = buf.getChannelData(0);
  const fl = fadeTime * ctx.sampleRate, fi1 = fl, fi2 = len1 - fl;
  for (let i = 0; i < len1; i++) {
    if (i < fi1) p[i] = Math.sqrt(i / fl);
    else if (i >= fi2) p[i] = Math.sqrt(1 - (i - fi2) / fl);
    else p[i] = 1;
  }
  for (let i = len1; i < length; i++) p[i] = 0;
  return buf;
}

function createDelayBuffer(ctx, activeTime, fadeTime, shiftUp) {
  const len1 = activeTime * ctx.sampleRate, len2 = (activeTime - 2 * fadeTime) * ctx.sampleRate;
  const length = len1 + len2, buf = ctx.createBuffer(1, length, ctx.sampleRate), p = buf.getChannelData(0);
  for (let i = 0; i < len1; i++) p[i] = shiftUp ? (len1 - i) / length : i / len1;
  for (let i = len1; i < length; i++) p[i] = 0;
  return buf;
}

export function createPitchShifter(ctx) {
  const input = ctx.createGain(), output = ctx.createGain();
  const down = createDelayBuffer(ctx, bufferTime, fadeTime, false);
  const up = createDelayBuffer(ctx, bufferTime, fadeTime, true);
  const fadeBuf = createFadeBuffer(ctx, bufferTime, fadeTime);

  const mod1 = ctx.createBufferSource(), mod2 = ctx.createBufferSource();
  const mod3 = ctx.createBufferSource(), mod4 = ctx.createBufferSource();
  mod1.buffer = mod2.buffer = down; mod3.buffer = mod4.buffer = up;
  for (const m of [mod1, mod2, mod3, mod4]) m.loop = true;

  const mod1G = ctx.createGain(), mod2G = ctx.createGain();
  const mod3G = ctx.createGain(), mod4G = ctx.createGain();
  mod3G.gain.value = mod4G.gain.value = 0;
  mod1.connect(mod1G); mod2.connect(mod2G); mod3.connect(mod3G); mod4.connect(mod4G);

  const modGain1 = ctx.createGain(), modGain2 = ctx.createGain();
  const delay1 = ctx.createDelay(), delay2 = ctx.createDelay();
  mod1G.connect(modGain1); mod3G.connect(modGain1);
  mod2G.connect(modGain2); mod4G.connect(modGain2);
  modGain1.connect(delay1.delayTime); modGain2.connect(delay2.delayTime);

  const fade1 = ctx.createBufferSource(), fade2 = ctx.createBufferSource();
  fade1.buffer = fade2.buffer = fadeBuf; fade1.loop = fade2.loop = true;
  const mix1 = ctx.createGain(), mix2 = ctx.createGain();
  mix1.gain.value = mix2.gain.value = 0;
  fade1.connect(mix1.gain); fade2.connect(mix2.gain);

  input.connect(delay1); input.connect(delay2);
  delay1.connect(mix1); delay2.connect(mix2);
  mix1.connect(output); mix2.connect(output);

  const t = ctx.currentTime + 0.05, t2 = t + bufferTime - fadeTime;
  mod1.start(t); mod2.start(t2); mod3.start(t); mod4.start(t2);
  fade1.start(t); fade2.start(t2);

  const setDelay = (d) => {
    modGain1.gain.setTargetAtTime(0.5 * d, ctx.currentTime, 0.01);
    modGain2.gain.setTargetAtTime(0.5 * d, ctx.currentTime, 0.01);
  };
  // mult: >0 pitch up, <0 pitch down; ±1 ≈ ±1 octave
  function setPitchOffset(mult) {
    const up = mult > 0;
    mod1G.gain.value = up ? 0 : 1; mod2G.gain.value = up ? 0 : 1;
    mod3G.gain.value = up ? 1 : 0; mod4G.gain.value = up ? 1 : 0;
    setDelay(delayTime * Math.abs(mult));
  }
  setDelay(delayTime); setPitchOffset(0);

  // map semitones -> mult (exact at the octave)
  function setSemitones(n) {
    setPitchOffset(n >= 0 ? Math.pow(2, n / 12) - 1 : 1 - Math.pow(2, -n / 12));
  }

  return { input, output, setSemitones };
}
