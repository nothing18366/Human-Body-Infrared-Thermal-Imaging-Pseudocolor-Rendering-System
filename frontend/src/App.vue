<template>
  <div class="page">
    <header class="topbar">
      <div>
        <h1>人体红外热成像检测伪彩渲染</h1>
        <p>XML + 温度矩阵 + Canvas动态重绘</p>
      </div>
      <div class="patient" v-if="caseInfo">
        <span>编号：{{ caseInfo.snun }}</span>
        <span>性别：{{ caseInfo.gender }}</span>
        <span>年龄：{{ caseInfo.age }}</span>
      </div>
    </header>

    <main class="workspace">
      <section class="viewer-card">
        <div class="viewer-title">
          <div>
            <h2>{{ currentMeta?.title || '图像' }}</h2>
            <p v-if="currentMeta?.hasMatrix">
              矩阵：{{ currentMeta.width }} × {{ currentMeta.height }}，真实温度范围：{{ dataMin?.toFixed(2) }}℃ ~ {{ dataMax?.toFixed(2) }}℃
            </p>
            <p v-else class="warning">该图暂未提供温度矩阵，只能显示原始JPG预览。</p>
          </div>
          <button class="btn" @click="resetControls">恢复默认温标</button>
        </div>

        <div class="canvas-wrap">
          <canvas ref="thermalCanvas" class="thermal-canvas"></canvas>
        </div>

        <div class="thumbs">
          <button
            v-for="img in images"
            :key="img.id"
            class="thumb"
            :class="{ active: img.id === selectedId }"
            @click="selectImage(img.id)"
          >
            <img :src="BASE_URL + img.imageUrl" alt="thumbnail" />
            <span>{{ img.title }}</span>
            <small>{{ img.hasMatrix ? '可重绘' : '缺矩阵' }}</small>
          </button>
        </div>
      </section>

      <aside class="control-card">
        <h2>右侧滑动控制区</h2>

        <div class="notice">
          默认温标采用当前温度矩阵的P2~P98分位数；CLAHE只用于显示增强，不改变真实温度矩阵。
        </div>

        <div class="group">
          <label>温位：{{ levelTemp.toFixed(2) }}℃</label>
          <input
            type="range"
            :min="sliderMin"
            :max="sliderMax"
            step="0.05"
            v-model.number="levelTemp"
            @input="render"
          />
        </div>

        <div class="group">
          <label>温宽：{{ windowTemp.toFixed(1) }}℃</label>
          <input
            type="range"
            min="1"
            :max="windowMax"
            step="0.1"
            v-model.number="windowTemp"
            @input="render"
          />
        </div>

        <div class="range-info">
          <span>显示最低温：{{ minTemp.toFixed(2) }}℃</span>
          <span>显示最高温：{{ maxTemp.toFixed(2) }}℃</span>
        </div>

        <div class="group">
          <label>对比度Gamma：{{ gamma.toFixed(2) }}</label>
          <input
            type="range"
            min="0.60"
            max="1.60"
            step="0.05"
            v-model.number="gamma"
            @input="render"
          />
        </div>

        <div class="group">
          <label>锐化程度：{{ sharpness.toFixed(2) }}</label>
          <input
            type="range"
            min="0"
            max="0.80"
            step="0.05"
            v-model.number="sharpness"
            @input="render"
          />
        </div>

        <div class="group checkbox">
          <input id="clahe" type="checkbox" v-model="enableClahe" @change="render" />
          <label for="clahe">启用CLAHE局部对比度增强</label>
        </div>

        <div class="group" v-if="enableClahe">
          <label>CLAHE增强强度：{{ claheStrength.toFixed(2) }}</label>
          <input
            type="range"
            min="0"
            max="1"
            step="0.05"
            v-model.number="claheStrength"
            @input="render"
          />
        </div>

        <div class="group" v-if="enableClahe">
          <label>CLAHE裁剪阈值：{{ claheClipLimit.toFixed(1) }}</label>
          <input
            type="range"
            min="1.0"
            max="5.0"
            step="0.1"
            v-model.number="claheClipLimit"
            @input="render"
          />
        </div>

        <div class="group" v-if="enableClahe">
          <label>CLAHE局部块大小：{{ claheTileSize }}px</label>
          <input
            type="range"
            min="24"
            max="96"
            step="8"
            v-model.number="claheTileSize"
            @input="render"
          />
        </div>

        <div class="group">
          <label>色带</label>
          <select v-model="palette" @change="render">
            <option value="thermal">分级热成像</option>
            <option value="rainbow">彩虹</option>
            <option value="iron">铁红</option>
            <option value="gray">灰度</option>
          </select>
        </div>

        <div class="group checkbox">
          <input id="roi" type="checkbox" v-model="showRoi" @change="render" />
          <label for="roi">显示ROI标注</label>
        </div>

        <div class="colorbar" :style="colorbarStyle"></div>

        <div class="roi-list" v-if="currentMeta?.rois?.length">
          <h3>ROI点位</h3>
          <div v-for="roi in currentMeta.rois" :key="roi.name" class="roi-item">
            {{ roi.name }} / {{ roi.type }} / {{ roi.points.length }}点
          </div>
        </div>

        <div class="result" v-if="caseInfo?.result">
          <h3>XML检测描述</h3>
          <p>{{ caseInfo.result }}</p>
        </div>
      </aside>
    </main>
  </div>
</template>

<script setup>
import { computed, nextTick, onMounted, ref } from 'vue'

const BASE_URL = 'http://127.0.0.1:8000'

const thermalCanvas = ref(null)
const caseInfo = ref(null)
const images = ref([])
const selectedId = ref(0)
const currentMeta = ref(null)
const matrix = ref(null)
const dataMin = ref(null)
const dataMax = ref(null)

// 默认值只作为接口数据未加载时的兜底值。真正加载矩阵后，会在resetControls()里用P2~P98自动重置。
const levelTemp = ref(36.8)
const windowTemp = ref(6.5)
const gamma = ref(0.95)
const sharpness = ref(0.25)
const enableClahe = ref(true)
const claheStrength = ref(0.60)
const claheClipLimit = ref(2.5)
const claheTileSize = ref(48)
const palette = ref('thermal')
const showRoi = ref(true)

const minTemp = computed(() => levelTemp.value - windowTemp.value / 2)
const maxTemp = computed(() => levelTemp.value + windowTemp.value / 2)
const colorbarStyle = computed(() => ({ background: paletteCss(palette.value) }))

const sliderMin = computed(() => {
  if (dataMin.value == null) return 20
  return Math.floor(dataMin.value - 2)
})

const sliderMax = computed(() => {
  if (dataMax.value == null) return 45
  return Math.ceil(dataMax.value + 2)
})

const windowMax = computed(() => {
  if (dataMin.value == null || dataMax.value == null) return 25
  return Math.max(5, Math.ceil(dataMax.value - dataMin.value + 4))
})

onMounted(async () => {
  await loadCase()
  await selectImage(0)
})

async function loadCase() {
  const res = await fetch(`${BASE_URL}/api/case`)
  const data = await res.json()
  caseInfo.value = data.case
  images.value = data.images
}

async function selectImage(id) {
  selectedId.value = id

  const res = await fetch(`${BASE_URL}/api/images/${id}`)
  const data = await res.json()

  currentMeta.value = data.meta
  dataMin.value = data.dataMin
  dataMax.value = data.dataMax
  matrix.value = data.matrix?.length ? new Float32Array(data.matrix) : null

  resetControls()
  await nextTick()
  render()
}

function resetControls() {
  if (matrix.value && matrix.value.length) {
    // 模拟商业热成像软件的自动Level/Span：用分位数避免极端值拉宽温标。
    const pLow = percentile(matrix.value, 2)
    const pHigh = percentile(matrix.value, 98)
    const span = Math.max(2.5, pHigh - pLow)
    const center = (pLow + pHigh) / 2

    levelTemp.value = center
    windowTemp.value = span
    gamma.value = 0.95
    sharpness.value = 0.25
    enableClahe.value = true
    claheStrength.value = 0.60
    claheClipLimit.value = 2.5
    claheTileSize.value = 48
    palette.value = 'thermal'
  } else if (dataMin.value != null && dataMax.value != null) {
    levelTemp.value = (dataMin.value + dataMax.value) / 2
    windowTemp.value = Math.max(1, dataMax.value - dataMin.value)
    gamma.value = 1.0
    sharpness.value = 0.15
    enableClahe.value = false
    palette.value = 'thermal'
  } else {
    levelTemp.value = 36.8
    windowTemp.value = 6.5
    gamma.value = 0.95
    sharpness.value = 0.25
    enableClahe.value = true
    claheStrength.value = 0.60
    claheClipLimit.value = 2.5
    claheTileSize.value = 48
    palette.value = 'thermal'
  }

  render()
}

function render() {
  const canvas = thermalCanvas.value
  if (!canvas || !currentMeta.value) return

  const ctx = canvas.getContext('2d')
  const width = Number(currentMeta.value.width || 460)
  const height = Number(currentMeta.value.height || 620)
  canvas.width = width
  canvas.height = height

  if (!matrix.value) {
    drawOriginalPreview(canvas, ctx, width, height)
    return
  }

  // 注意：所有增强都只作用在显示流程，不改变原始温度矩阵。
  const enhancedTemp = sharpness.value > 0 ? unsharpMask(matrix.value, width, height, sharpness.value) : matrix.value
  const normalized = normalizeToUint8(enhancedTemp, minTemp.value, maxTemp.value)

  let displayGray = normalized
  if (enableClahe.value) {
    const claheGray = claheEnhance(normalized, width, height, {
      tileSize: claheTileSize.value,
      clipLimit: claheClipLimit.value,
      bins: 256,
    })
    displayGray = blendUint8(normalized, claheGray, claheStrength.value)
  }

  const imageData = ctx.createImageData(width, height)
  const buf = imageData.data

  for (let i = 0; i < displayGray.length; i++) {
    const p = i * 4
    let v = displayGray[i] / 255

    // Gamma只控制显示对比度，不改变真实温度矩阵。
    v = Math.pow(v, gamma.value)

    const [r, g, b] = pseudoColor(v, palette.value)
    buf[p] = r
    buf[p + 1] = g
    buf[p + 2] = b
    buf[p + 3] = 255
  }

  ctx.putImageData(imageData, 0, 0)

  if (showRoi.value) {
    drawRois(ctx)
  }
}

function drawOriginalPreview(canvas, ctx, width, height) {
  ctx.clearRect(0, 0, width, height)
  ctx.fillStyle = '#ffffff'
  ctx.fillRect(0, 0, width, height)

  const img = new Image()
  img.crossOrigin = 'anonymous'
  img.onload = () => {
    ctx.drawImage(img, 0, 0, width, height)
    if (showRoi.value) drawRois(ctx)
  }
  img.src = BASE_URL + currentMeta.value.imageUrl
}

function normalizeToUint8(src, minValue, maxValue) {
  const out = new Uint8Array(src.length)
  const denom = Math.max(0.0001, maxValue - minValue)

  for (let i = 0; i < src.length; i++) {
    let v = (src[i] - minValue) / denom
    if (v < 0) v = 0
    if (v > 1) v = 1
    out[i] = Math.round(v * 255)
  }

  return out
}

function blendUint8(a, b, weightB) {
  const out = new Uint8Array(a.length)
  const wb = Math.max(0, Math.min(1, weightB))
  const wa = 1 - wb

  for (let i = 0; i < a.length; i++) {
    out[i] = Math.round(a[i] * wa + b[i] * wb)
  }

  return out
}

function claheEnhance(gray, width, height, options = {}) {
  const bins = options.bins || 256
  const tileSize = Math.max(8, Math.floor(options.tileSize || 48))
  const clipLimit = Math.max(1, Number(options.clipLimit || 2.5))

  const tilesX = Math.ceil(width / tileSize)
  const tilesY = Math.ceil(height / tileSize)
  const luts = new Array(tilesX * tilesY)

  for (let ty = 0; ty < tilesY; ty++) {
    for (let tx = 0; tx < tilesX; tx++) {
      const x0 = tx * tileSize
      const y0 = ty * tileSize
      const x1 = Math.min(width, x0 + tileSize)
      const y1 = Math.min(height, y0 + tileSize)
      luts[ty * tilesX + tx] = buildClaheLut(gray, width, x0, y0, x1, y1, bins, clipLimit)
    }
  }

  const out = new Uint8Array(gray.length)

  for (let y = 0; y < height; y++) {
    const gy = y / tileSize - 0.5
    const yLow = clampInt(Math.floor(gy), 0, tilesY - 1)
    const yHigh = clampInt(yLow + 1, 0, tilesY - 1)
    const fy = clamp01(gy - Math.floor(gy))

    for (let x = 0; x < width; x++) {
      const gx = x / tileSize - 0.5
      const xLow = clampInt(Math.floor(gx), 0, tilesX - 1)
      const xHigh = clampInt(xLow + 1, 0, tilesX - 1)
      const fx = clamp01(gx - Math.floor(gx))

      const value = gray[y * width + x]
      const lut00 = luts[yLow * tilesX + xLow]
      const lut10 = luts[yLow * tilesX + xHigh]
      const lut01 = luts[yHigh * tilesX + xLow]
      const lut11 = luts[yHigh * tilesX + xHigh]

      const top = lut00[value] * (1 - fx) + lut10[value] * fx
      const bottom = lut01[value] * (1 - fx) + lut11[value] * fx
      out[y * width + x] = Math.round(top * (1 - fy) + bottom * fy)
    }
  }

  return out
}

function buildClaheLut(gray, width, x0, y0, x1, y1, bins, clipLimit) {
  const hist = new Array(bins).fill(0)
  let pixelCount = 0

  for (let y = y0; y < y1; y++) {
    for (let x = x0; x < x1; x++) {
      hist[gray[y * width + x]]++
      pixelCount++
    }
  }

  if (pixelCount === 0) {
    return Array.from({ length: bins }, (_, i) => i)
  }

  // clipLimit不是绝对像素数，而是相对平均桶高度的倍数。
  const avgBinCount = pixelCount / bins
  const clipAbs = Math.max(1, Math.floor(clipLimit * avgBinCount))
  let clipped = 0

  for (let i = 0; i < bins; i++) {
    if (hist[i] > clipAbs) {
      clipped += hist[i] - clipAbs
      hist[i] = clipAbs
    }
  }

  const redist = Math.floor(clipped / bins)
  const residual = clipped % bins
  for (let i = 0; i < bins; i++) hist[i] += redist
  for (let i = 0; i < residual; i++) hist[i]++

  const lut = new Uint8Array(bins)
  let cdf = 0
  for (let i = 0; i < bins; i++) {
    cdf += hist[i]
    lut[i] = Math.max(0, Math.min(255, Math.round((cdf / pixelCount) * 255)))
  }

  return lut
}

function clamp01(v) {
  if (v < 0) return 0
  if (v > 1) return 1
  return v
}

function clampInt(v, min, max) {
  if (v < min) return min
  if (v > max) return max
  return v
}

function percentile(arr, p) {
  const values = Array.from(arr)
    .filter(v => Number.isFinite(v))
    .sort((a, b) => a - b)

  if (!values.length) return 0

  const index = (p / 100) * (values.length - 1)
  const low = Math.floor(index)
  const high = Math.ceil(index)

  if (low === high) return values[low]

  const t = index - low
  return values[low] * (1 - t) + values[high] * t
}

function unsharpMask(src, width, height, amount) {
  const out = new Float32Array(src.length)

  for (let y = 0; y < height; y++) {
    for (let x = 0; x < width; x++) {
      let sum = 0
      let count = 0

      for (let dy = -1; dy <= 1; dy++) {
        const yy = y + dy
        if (yy < 0 || yy >= height) continue
        for (let dx = -1; dx <= 1; dx++) {
          const xx = x + dx
          if (xx < 0 || xx >= width) continue
          sum += src[yy * width + xx]
          count++
        }
      }

      const i = y * width + x
      const blur = sum / count
      out[i] = src[i] + amount * (src[i] - blur)
    }
  }

  return out
}

function drawRois(ctx) {
  const rois = currentMeta.value?.rois || []
  ctx.save()
  ctx.lineWidth = 2
  ctx.font = '14px Microsoft YaHei, Arial'
  ctx.textBaseline = 'bottom'

  for (const roi of rois) {
    if (!roi.points?.length) continue

    if (roi.type === 'line' && roi.points.length >= 2) {
      const p1 = roi.points[0]
      const p2 = roi.points[1]
      ctx.strokeStyle = '#ff2d55'
      ctx.fillStyle = '#ff2d55'
      ctx.beginPath()
      ctx.moveTo(p1.x, p1.y)
      ctx.lineTo(p2.x, p2.y)
      ctx.stroke()
      ctx.fillText(roi.name, p1.x + 6, p1.y - 4)
    } else {
      const cx = roi.points.reduce((s, p) => s + p.x, 0) / roi.points.length
      const cy = roi.points.reduce((s, p) => s + p.y, 0) / roi.points.length
      ctx.strokeStyle = '#ff2d55'
      ctx.fillStyle = '#ff2d55'
      ctx.beginPath()
      ctx.arc(cx, cy, 6, 0, Math.PI * 2)
      ctx.stroke()
      ctx.fillText(roi.name, cx + 8, cy - 6)
    }
  }
  ctx.restore()
}

function pseudoColor(v, name) {
  if (name === 'gray') {
    const g = Math.round(v * 255)
    return [g, g, g]
  }

  if (name === 'iron') {
    return interpolatePalette(v, [
      [0, 0, 0],
      [75, 0, 130],
      [160, 30, 0],
      [255, 120, 0],
      [255, 230, 130],
      [255, 255, 255],
    ])
  }

  if (name === 'rainbow') {
    return interpolatePalette(v, [
      [30, 0, 120],
      [0, 0, 220],
      [0, 200, 255],
      [0, 220, 70],
      [255, 240, 0],
      [255, 80, 0],
      [255, 0, 160],
    ])
  }

  // 接近示例图的“蓝-青-绿-黄-红-紫”伪彩色带。
  return interpolatePalette(v, [
    [0, 0, 70],
    [0, 0, 200],
    [0, 200, 255],
    [40, 220, 80],
    [230, 230, 40],
    [255, 40, 30],
    [230, 0, 180],
  ])
}

function interpolatePalette(v, colors) {
  const n = colors.length - 1
  const p = v * n
  const i = Math.min(Math.floor(p), n - 1)
  const t = p - i
  const c1 = colors[i]
  const c2 = colors[i + 1]
  return [
    Math.round(c1[0] + (c2[0] - c1[0]) * t),
    Math.round(c1[1] + (c2[1] - c1[1]) * t),
    Math.round(c1[2] + (c2[2] - c1[2]) * t),
  ]
}

function paletteCss(name) {
  if (name === 'gray') return 'linear-gradient(to top, #000, #fff)'
  if (name === 'iron') return 'linear-gradient(to top, #000, #4b0082, #a01e00, #ff7800, #ffe682, #fff)'
  if (name === 'rainbow') return 'linear-gradient(to top, rgb(30,0,120), blue, cyan, lime, yellow, orange, rgb(255,0,160))'
  return 'linear-gradient(to top, rgb(0,0,70), blue, cyan, rgb(40,220,80), yellow, red, rgb(230,0,180))'
}
</script>

<style scoped>
* {
  box-sizing: border-box;
}

.page {
  min-height: 100vh;
  background: #eef2f7;
  color: #1f2937;
  padding: 20px;
  font-family: "Microsoft YaHei", Arial, sans-serif;
}

.topbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  background: #fff;
  border-radius: 18px;
  padding: 18px 22px;
  box-shadow: 0 8px 24px rgba(15, 23, 42, 0.08);
  margin-bottom: 18px;
}

.topbar h1 {
  margin: 0;
  font-size: 24px;
}

.topbar p {
  margin: 6px 0 0;
  color: #64748b;
}

.patient {
  display: flex;
  gap: 14px;
  color: #475569;
  font-size: 14px;
}

.workspace {
  display: grid;
  grid-template-columns: minmax(520px, 1fr) 360px;
  gap: 18px;
  align-items: start;
}

.viewer-card,
.control-card {
  background: #fff;
  border-radius: 18px;
  padding: 18px;
  box-shadow: 0 8px 24px rgba(15, 23, 42, 0.08);
}

.viewer-title {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12px;
}

.viewer-title h2,
.control-card h2 {
  margin: 0;
  font-size: 20px;
}

.viewer-title p {
  margin: 6px 0 0;
  color: #64748b;
}

.warning {
  color: #dc2626 !important;
}

.btn {
  border: none;
  background: #1f2937;
  color: #fff;
  padding: 9px 14px;
  border-radius: 12px;
  cursor: pointer;
}

.canvas-wrap {
  height: calc(100vh - 270px);
  min-height: 520px;
  display: flex;
  justify-content: center;
  align-items: center;
  background: #f8fafc;
  border: 1px solid #e2e8f0;
  border-radius: 16px;
  overflow: hidden;
}

.thermal-canvas {
  max-height: 100%;
  max-width: 100%;
  background: #fff;
  image-rendering: auto;
}

.thumbs {
  margin-top: 14px;
  display: grid;
  grid-template-columns: repeat(5, 1fr);
  gap: 10px;
}

.thumb {
  border: 2px solid transparent;
  background: #f8fafc;
  border-radius: 14px;
  padding: 8px;
  cursor: pointer;
  text-align: center;
}

.thumb.active {
  border-color: #2563eb;
  background: #eff6ff;
}

.thumb img {
  width: 100%;
  height: 110px;
  object-fit: contain;
  display: block;
}

.thumb span,
.thumb small {
  display: block;
}

.thumb span {
  font-size: 13px;
  margin-top: 4px;
}

.thumb small {
  color: #64748b;
}

.control-card {
  position: sticky;
  top: 20px;
}

.notice {
  margin-top: 12px;
  padding: 10px 12px;
  background: #f8fafc;
  border: 1px solid #e2e8f0;
  border-radius: 12px;
  color: #475569;
  font-size: 13px;
  line-height: 1.6;
}

.group {
  margin-top: 18px;
}

.group label {
  display: block;
  font-weight: 600;
  margin-bottom: 8px;
}

.group input[type="range"],
.group select {
  width: 100%;
}

.group select {
  height: 38px;
  border: 1px solid #cbd5e1;
  border-radius: 10px;
  padding: 0 10px;
  background: #fff;
}

.checkbox {
  display: flex;
  gap: 8px;
  align-items: center;
}

.checkbox label {
  margin: 0;
}

.range-info {
  margin-top: 10px;
  display: grid;
  gap: 6px;
  color: #475569;
  font-size: 14px;
}

.colorbar {
  height: 180px;
  width: 26px;
  border-radius: 999px;
  border: 1px solid #cbd5e1;
  margin: 18px auto;
}

.roi-list,
.result {
  margin-top: 18px;
  background: #f8fafc;
  border-radius: 14px;
  padding: 12px;
}

.roi-list h3,
.result h3 {
  margin: 0 0 8px;
  font-size: 15px;
}

.roi-item {
  font-size: 14px;
  color: #475569;
  margin: 4px 0;
}

.result p {
  white-space: pre-wrap;
  line-height: 1.7;
  margin: 0;
  color: #475569;
  font-size: 14px;
  max-height: 200px;
  overflow: auto;
}

@media (max-width: 980px) {
  .workspace {
    grid-template-columns: 1fr;
  }

  .control-card {
    position: static;
  }
}
</style>
