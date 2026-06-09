<template>
  <div class="page">
    <header class="topbar">
      <div>
        <h1>人体红外热成像检测伪彩渲染 V3.0 医疗增强版（背景替换）</h1>
        <p>温度矩阵 + 完整增强链（双边/CLAHE/Sobel/等温区）</p>
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
              矩阵：{{ currentMeta.width }} × {{ currentMeta.height }}，
              真实温度范围：{{ dataMin?.toFixed(2) }}℃ ~ {{ dataMax?.toFixed(2) }}℃
            </p>
            <p v-else class="warning">该图暂未提供温度矩阵，只能显示原始JPG预览。</p>
          </div>
          <button class="btn" @click="resetControls">恢复默认医疗参数</button>
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

        <div class="info-card" v-if="(currentMeta?.rois?.length || caseInfo?.result)">
          <div class="info-col" v-if="currentMeta?.rois?.length">
            <h3>ROI点位</h3>
            <div class="roi-list">
              <div v-for="roi in currentMeta.rois" :key="roi.name" class="roi-item">
                {{ roi.name }} / {{ roi.type }} / {{ roi.points.length }}点
              </div>
            </div>
          </div>
          <div class="info-col" v-if="caseInfo?.result">
            <h3>XML检测描述</h3>
            <p class="result-text">{{ caseInfo.result }}</p>
          </div>
        </div>
      </section>

      <aside class="control-card">
        <h2>显示控制区</h2>

        <div class="notice">
          默认采用当前温度矩阵的P2~P98分位数自动温标；所有增强只改变显示效果，不改变原始温度数据。
        </div>

        <div class="group">
          <label>温位：{{ levelTemp.toFixed(2) }}℃</label>
          <input type="range" :min="sliderMin" :max="sliderMax" step="0.05" v-model.number="levelTemp" @input="render" />
        </div>

        <div class="group">
          <label>温宽：{{ windowTemp.toFixed(1) }}℃</label>
          <input type="range" min="1" :max="windowMax" step="0.1" v-model.number="windowTemp" @input="render" />
        </div>

        <div class="range-info">
          <span>显示最低温：{{ minTemp.toFixed(2) }}℃</span>
          <span>显示最高温：{{ maxTemp.toFixed(2) }}℃</span>
        </div>

        <details class="advanced-group">
          <summary><strong>📊 对比度优化 V1.0</strong></summary>

          <div class="group">
            <label>对比度Gamma：{{ gamma.toFixed(2) }}</label>
            <input type="range" min="0.60" max="1.60" step="0.05" v-model.number="gamma" @input="render" />
          </div>

          <div class="group">
            <label>USM锐化程度：{{ sharpness.toFixed(2) }}</label>
            <input type="range" min="0" max="0.80" step="0.05" v-model.number="sharpness" @input="render" />
          </div>

          <div class="group checkbox">
            <input id="clahe" type="checkbox" v-model="enableClahe" @change="render" />
            <label for="clahe">启用CLAHE局部对比度增强</label>
          </div>

          <div class="group" v-if="enableClahe">
            <label>CLAHE增强强度：{{ claheStrength.toFixed(2) }}</label>
            <input type="range" min="0" max="1" step="0.05" v-model.number="claheStrength" @input="render" />
          </div>

          <div class="group" v-if="enableClahe">
            <label>CLAHE裁剪阈值：{{ claheClipLimit.toFixed(1) }}</label>
            <input type="range" min="1.0" max="5.0" step="0.1" v-model.number="claheClipLimit" @input="render" />
          </div>

          <div class="group" v-if="enableClahe">
            <label>CLAHE局部块大小：{{ claheTileSize }}px</label>
            <input type="range" min="24" max="96" step="8" v-model.number="claheTileSize" @input="render" />
          </div>
        </details>

        <!-- V2.0 高级增强面板（可折叠） -->
        <details class="advanced-group">
          <summary><strong>⚙️ 医疗增强 V2.0</strong></summary>

          <div class="group checkbox">
            <input id="bilateral" type="checkbox" v-model="enableBilateral" @change="render" />
            <label for="bilateral">启用双边滤波降噪</label>
          </div>
          <div class="group" v-if="enableBilateral">
            <label>空间平滑度：{{ bilateralSpaceSigma.toFixed(1) }}</label>
            <input type="range" min="0.5" max="4.0" step="0.1" v-model.number="bilateralSpaceSigma" @input="render" />
          </div>
          <div class="group" v-if="enableBilateral">
            <label>温度相似阈值：{{ bilateralRangeSigma.toFixed(2) }}℃</label>
            <input type="range" min="0.1" max="2.0" step="0.05" v-model.number="bilateralRangeSigma" @input="render" />
          </div>

          <div class="group checkbox">
            <input id="sobel" type="checkbox" v-model="enableSobel" @change="render" />
            <label for="sobel">启用Sobel边缘增强</label>
          </div>
          <div class="group" v-if="enableSobel">
            <label>Sobel强度：{{ sobelStrength.toFixed(2) }}</label>
            <input type="range" min="0" max="0.5" step="0.02" v-model.number="sobelStrength" @input="render" />
          </div>

          <div class="group checkbox">
            <input id="isotherm" type="checkbox" v-model="enableIsotherm" @change="render" />
            <label for="isotherm">启用等温区分层</label>
          </div>
          <div class="group" v-if="enableIsotherm">
            <label>等温区数量：{{ isothermLevels }}</label>
            <input type="range" min="3" max="20" step="1" v-model.number="isothermLevels" @input="render" />
          </div>
        </details>

        <details class="advanced-group">
          <summary><strong>🖼️ 背景替换 V3.0</strong></summary>

          <div class="group checkbox">
            <input id="bgReplace" type="checkbox" v-model="enableBackgroundReplace" @change="render" />
            <label for="bgReplace">启用背景替换（白色背景）</label>
          </div>

          <div class="group" v-if="enableBackgroundReplace">
            <label>分割阈值偏移：{{ bgThresholdOffset.toFixed(1) }}℃</label>
            <input type="range" min="-2.0" max="2.0" step="0.1" v-model.number="bgThresholdOffset" @input="render" />
            <small style="color: #64748b;">负值扩大身体区域，正值缩小身体区域</small>
          </div>

          <div class="group" v-if="enableBackgroundReplace">
            <label>边缘平滑度：{{ bgEdgeSmoothing.toFixed(1) }}</label>
            <input type="range" min="0.5" max="6.0" step="0.5" v-model.number="bgEdgeSmoothing" @input="render" />
            <small style="color: #64748b;">值越大边缘越柔和，值越小边缘越锐利</small>
          </div>
        </details>

        <div class="inline-row">
          <div class="group" style="flex:1">
            <label>色带</label>
            <select v-model="palette" @change="render">
              <option value="thermal">分级热成像</option>
              <option value="medical">医疗色带</option>
              <option value="rainbow">彩虹</option>
              <option value="iron">铁红</option>
              <option value="gray">灰度</option>
            </select>
          </div>
          <div class="group checkbox" style="flex:0 0 auto;align-self:flex-end;padding-bottom:2px">
            <input id="roi" type="checkbox" v-model="showRoi" @change="render" />
            <label for="roi">显示ROI</label>
          </div>
        </div>

        <div class="colorbar" :style="colorbarStyle"></div>

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

// ---------- 基础显示参数 ----------
const levelTemp = ref(40.6)
const windowTemp = ref(3.0)
const gamma = ref(0.95)
const sharpness = ref(0.20)               // USM锐化量
const enableClahe = ref(true)
const claheStrength = ref(0.60)
const claheClipLimit = ref(2.5)
const claheTileSize = ref(48)
const palette = ref('thermal')             // V2.0默认使用分级热成像
const showRoi = ref(false)

// ---------- V2.0 医疗增强参数 ----------
const enableBilateral = ref(true)
const bilateralSpaceSigma = ref(1.5)
const bilateralRangeSigma = ref(0.60)
const enableSobel = ref(true)
const sobelStrength = ref(0.15)
const enableIsotherm = ref(true)
const isothermLevels = ref(10)

// ---------- V3.0 背景替换参数 ----------
const enableBackgroundReplace = ref(true)
const bgThresholdOffset = ref(0.0)
const bgEdgeSmoothing = ref(0.5)

// ---------- 计算属性 ----------
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

// ---------- 生命周期 ----------
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
  // V2.0 医疗模式固定默认温标
  levelTemp.value = 40.6
  windowTemp.value = 3.0

  // 医疗模式默认值（V2.0）
  gamma.value = 0.95
  sharpness.value = 0.20
  enableClahe.value = true
  claheStrength.value = 0.60
  claheClipLimit.value = 2.5
  claheTileSize.value = 48
  palette.value = 'thermal'

  enableBilateral.value = true
  bilateralSpaceSigma.value = 1.5
  bilateralRangeSigma.value = 0.60
  enableSobel.value = true
  sobelStrength.value = 0.15
  enableIsotherm.value = true
  isothermLevels.value = 10

  enableBackgroundReplace.value = true
  bgThresholdOffset.value = 0.0
  bgEdgeSmoothing.value = 0.5

  render()
}

// ========== 渲染核心（V2.0增强链） ==========
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

  // 1. 拷贝原始温度矩阵
  let working = new Float32Array(matrix.value)

  // 1.5 背景分割掩码（基于原始温度矩阵，V3.0）
  let bgMask = null
  if (enableBackgroundReplace.value) {
    const { hist, minV, maxV } = buildHistogram(matrix.value, 256)
    const otsuBin = computeOtsuThreshold(hist, width * height)
    const thresholdTemp = minV + (otsuBin / 255) * (maxV - minV) + bgThresholdOffset.value
    bgMask = createBinaryMask(matrix.value, width, height, thresholdTemp)
    morphologicalClose(bgMask, width, height, 1)
    keepLargestComponent(bgMask, width, height)
    morphologicalOpen(bgMask, width, height, 2)
    gaussianBlurMask(bgMask, width, height, bgEdgeSmoothing.value)
  }

  // 2. 双边滤波（Bilateral）
  if (enableBilateral.value) {
    working = bilateralFilter(working, width, height, bilateralSpaceSigma.value, bilateralRangeSigma.value)
  }

  // 3. CLAHE（临时映射到0-255灰度，增强后反变换）
  if (enableClahe.value) {
    const tempMin = minVal(working)
    const tempMax = maxVal(working)
    if (tempMax - tempMin > 1e-6) {
      const gray = normalizeToUint8(working, tempMin, tempMax)
      const claheGray = claheEnhance(gray, width, height, {
        tileSize: claheTileSize.value,
        clipLimit: claheClipLimit.value,
        bins: 256,
      })
      const blendedGray = blendUint8(gray, claheGray, claheStrength.value)
      // 反映射回温度域
      for (let i = 0; i < working.length; i++) {
        working[i] = tempMin + (blendedGray[i] / 255) * (tempMax - tempMin)
      }
    }
  }

  // 4. Sobel边缘增强
  if (enableSobel.value) {
    const grad = sobelMagnitude(working, width, height)
    for (let i = 0; i < working.length; i++) {
      working[i] += sobelStrength.value * grad[i]
    }
  }

  // 5. USM锐化（原有非锐化掩蔽）
  if (sharpness.value > 0) {
    working = unsharpMask(working, width, height, sharpness.value)
  }

  // 6. 归一化到用户设定的显示温标范围（minTemp~maxTemp）
  const normalized = normalizeToUint8(working, minTemp.value, maxTemp.value)

  // 7. 转为0-1浮点数组，用于后续等温区、Gamma、伪彩
  const vArray = new Float32Array(working.length)
  for (let i = 0; i < normalized.length; i++) {
    vArray[i] = normalized[i] / 255
  }

  // 8. 等温区分层（Isotherm）
  if (enableIsotherm.value) {
    const levels = isothermLevels.value
    for (let i = 0; i < vArray.length; i++) {
      vArray[i] = (Math.floor(vArray[i] * levels) + 0.5) / levels
    }
  }

  // 9. Gamma校正
  for (let i = 0; i < vArray.length; i++) {
    let v = vArray[i]
    v = Math.pow(v, gamma.value)
    if (v < 0) v = 0
    if (v > 1) v = 1
    vArray[i] = v
  }

  // 10. 医疗色带映射并绘制（V3.0 背景替换）
  const imageData = ctx.createImageData(width, height)
  const buf = imageData.data
  if (bgMask) {
    for (let i = 0; i < vArray.length; i++) {
      const p = i * 4
      const [r, g, b] = pseudoColor(vArray[i], palette.value)
      const alpha = bgMask[i]
      buf[p] = Math.round(r * alpha + 255 * (1 - alpha))
      buf[p + 1] = Math.round(g * alpha + 255 * (1 - alpha))
      buf[p + 2] = Math.round(b * alpha + 255 * (1 - alpha))
      buf[p + 3] = 255
    }
  } else {
    for (let i = 0; i < vArray.length; i++) {
      const p = i * 4
      const [r, g, b] = pseudoColor(vArray[i], palette.value)
      buf[p] = r
      buf[p + 1] = g
      buf[p + 2] = b
      buf[p + 3] = 255
    }
  }
  ctx.putImageData(imageData, 0, 0)

  // 叠加ROI
  if (showRoi.value) {
    drawRois(ctx)
  }
}

// ---------- 无矩阵时的预览 ----------
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

// ========== 工具函数 ==========
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

function minVal(arr) {
  let m = Infinity
  for (let i = 0; i < arr.length; i++) if (arr[i] < m) m = arr[i]
  return m
}

function maxVal(arr) {
  let m = -Infinity
  for (let i = 0; i < arr.length; i++) if (arr[i] > m) m = arr[i]
  return m
}

// ---------- 双边滤波 ----------
function bilateralFilter(src, width, height, sigmaSpace, sigmaRange) {
  const radius = Math.min(Math.ceil(sigmaSpace), 2)     // 最大5×5核
  const dst = new Float32Array(src.length)
  const kSize = 2 * radius + 1

  // 预计算空间高斯核（顺序：先dy后dx）
  const spaceKernel = []
  for (let dy = -radius; dy <= radius; dy++) {
    for (let dx = -radius; dx <= radius; dx++) {
      const d = (dx * dx + dy * dy) / (2 * sigmaSpace * sigmaSpace)
      spaceKernel.push(Math.exp(-d))
    }
  }

  for (let y = 0; y < height; y++) {
    for (let x = 0; x < width; x++) {
      const ci = y * width + x
      const cVal = src[ci]
      let sum = 0
      let wsum = 0
      let kIdx = 0
      for (let dy = -radius; dy <= radius; dy++) {
        const ny = y + dy
        for (let dx = -radius; dx <= radius; dx++) {
          const nx = x + dx
          const sk = spaceKernel[kIdx++]
          if (ny < 0 || ny >= height || nx < 0 || nx >= width) continue
          const nVal = src[ny * width + nx]
          const diff = nVal - cVal
          const vw = Math.exp(-(diff * diff) / (2 * sigmaRange * sigmaRange))
          const w = sk * vw
          sum += nVal * w
          wsum += w
        }
      }
      dst[ci] = wsum > 0 ? sum / wsum : cVal
    }
  }
  return dst
}

// ---------- Sobel梯度幅值 ----------
function sobelMagnitude(src, width, height) {
  const grad = new Float32Array(width * height)
  for (let y = 1; y < height - 1; y++) {
    for (let x = 1; x < width - 1; x++) {
      const tl = src[(y - 1) * width + (x - 1)]
      const tc = src[(y - 1) * width + x]
      const tr = src[(y - 1) * width + (x + 1)]
      const ml = src[y * width + (x - 1)]
      const mr = src[y * width + (x + 1)]
      const bl = src[(y + 1) * width + (x - 1)]
      const bc = src[(y + 1) * width + x]
      const br = src[(y + 1) * width + (x + 1)]
      const gx = -tl + tr - 2 * ml + 2 * mr - bl + br
      const gy = -tl - 2 * tc - tr + bl + 2 * bc + br
      grad[y * width + x] = Math.sqrt(gx * gx + gy * gy)
    }
  }
  return grad
}

// ---------- USM（非锐化掩蔽） ----------
function unsharpMask(src, width, height, amount) {
  const out = new Float32Array(src.length)
  for (let y = 0; y < height; y++) {
    for (let x = 0; x < width; x++) {
      let sum = 0, cnt = 0
      for (let dy = -1; dy <= 1; dy++) {
        const yy = y + dy
        if (yy < 0 || yy >= height) continue
        for (let dx = -1; dx <= 1; dx++) {
          const xx = x + dx
          if (xx < 0 || xx >= width) continue
          sum += src[yy * width + xx]
          cnt++
        }
      }
      const i = y * width + x
      const blur = sum / cnt
      out[i] = src[i] + amount * (src[i] - blur)
    }
  }
  return out
}

// ---------- CLAHE（与V1一致，移至此处） ----------
function claheEnhance(gray, width, height, options = {}) {
  const bins = options.bins || 256
  const tileSize = Math.max(8, Math.floor(options.tileSize || 48))
  const clipLimit = Math.max(1, Number(options.clipLimit || 2.5))
  const tilesX = Math.ceil(width / tileSize)
  const tilesY = Math.ceil(height / tileSize)
  const luts = new Array(tilesX * tilesY)

  for (let ty = 0; ty < tilesY; ty++) {
    for (let tx = 0; tx < tilesX; tx++) {
      const x0 = tx * tileSize, y0 = ty * tileSize
      const x1 = Math.min(width, x0 + tileSize), y1 = Math.min(height, y0 + tileSize)
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
      const bot = lut01[value] * (1 - fx) + lut11[value] * fx
      out[y * width + x] = Math.round(top * (1 - fy) + bot * fy)
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
  if (pixelCount === 0) return Array.from({ length: bins }, (_, i) => i)

  const avg = pixelCount / bins
  const clipAbs = Math.max(1, Math.floor(clipLimit * avg))
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

// ---------- 辅助钳位 ----------
function clamp01(v) { return v < 0 ? 0 : v > 1 ? 1 : v }
function clampInt(v, min, max) { return v < min ? min : v > max ? max : v }

// ---------- 分位数 ----------
function percentile(arr, p) {
  const values = Array.from(arr).filter(v => Number.isFinite(v)).sort((a, b) => a - b)
  if (!values.length) return 0
  const index = (p / 100) * (values.length - 1)
  const low = Math.floor(index), high = Math.ceil(index)
  if (low === high) return values[low]
  const t = index - low
  return values[low] * (1 - t) + values[high] * t
}

// ========== V3.0 背景分割管线 ==========
function buildHistogram(arr, bins = 256) {
  const minV = minVal(arr)
  const maxV = maxVal(arr)
  const hist = new Uint32Array(bins)
  const scale = (bins - 1) / Math.max(0.0001, maxV - minV)
  for (let i = 0; i < arr.length; i++) {
    const idx = Math.min(bins - 1, Math.max(0, Math.round((arr[i] - minV) * scale)))
    hist[idx]++
  }
  return { hist, minV, maxV }
}

function computeOtsuThreshold(hist, totalPixels) {
  const bins = hist.length
  let sumAll = 0
  for (let i = 0; i < bins; i++) sumAll += i * hist[i]

  let weightBg = 0
  let sumBg = 0
  let maxVariance = 0
  let bestBin = 0

  for (let t = 0; t < bins; t++) {
    weightBg += hist[t]
    if (weightBg === 0) continue
    const weightFg = totalPixels - weightBg
    if (weightFg === 0) break
    sumBg += t * hist[t]
    const meanBg = sumBg / weightBg
    const meanFg = (sumAll - sumBg) / weightFg
    const variance = weightBg * weightFg * (meanBg - meanFg) * (meanBg - meanFg)
    if (variance > maxVariance) {
      maxVariance = variance
      bestBin = t
    }
  }
  return bestBin
}

function createBinaryMask(arr, width, height, thresholdTemp) {
  const mask = new Float32Array(width * height)
  for (let i = 0; i < arr.length; i++) {
    mask[i] = arr[i] >= thresholdTemp ? 1.0 : 0.0
  }
  return mask
}

function morphologicalDilate(mask, width, height, radius = 1) {
  const out = new Float32Array(mask.length)
  for (let y = 0; y < height; y++) {
    for (let x = 0; x < width; x++) {
      let maxVal = 0
      for (let dy = -radius; dy <= radius; dy++) {
        const ny = y + dy
        if (ny < 0 || ny >= height) continue
        for (let dx = -radius; dx <= radius; dx++) {
          const nx = x + dx
          if (nx < 0 || nx >= width) continue
          if (mask[ny * width + nx] > maxVal) maxVal = mask[ny * width + nx]
        }
      }
      out[y * width + x] = maxVal
    }
  }
  for (let i = 0; i < mask.length; i++) mask[i] = out[i]
}

function morphologicalErode(mask, width, height, radius = 1) {
  const out = new Float32Array(mask.length)
  for (let y = 0; y < height; y++) {
    for (let x = 0; x < width; x++) {
      let minVal = 1
      for (let dy = -radius; dy <= radius; dy++) {
        const ny = y + dy
        if (ny < 0 || ny >= height) continue
        for (let dx = -radius; dx <= radius; dx++) {
          const nx = x + dx
          if (nx < 0 || nx >= width) continue
          if (mask[ny * width + nx] < minVal) minVal = mask[ny * width + nx]
        }
      }
      out[y * width + x] = minVal
    }
  }
  for (let i = 0; i < mask.length; i++) mask[i] = out[i]
}

function morphologicalClose(mask, width, height, radius) {
  morphologicalDilate(mask, width, height, radius)
  morphologicalErode(mask, width, height, radius)
}

function morphologicalOpen(mask, width, height, radius) {
  morphologicalErode(mask, width, height, radius)
  morphologicalDilate(mask, width, height, radius)
}

function keepLargestComponent(mask, width, height) {
  const labels = new Int32Array(mask.length).fill(-1)
  const parent = []
  const size = []

  function findRoot(p, label) {
    while (p[label] !== label) {
      p[label] = p[p[label]]
      label = p[label]
    }
    return label
  }

  // Pass 1: label and record equivalences
  let nextLabel = 0
  for (let y = 0; y < height; y++) {
    for (let x = 0; x < width; x++) {
      const idx = y * width + x
      if (mask[idx] < 0.5) continue

      const left = (x > 0) ? labels[y * width + (x - 1)] : -1
      const up = (y > 0) ? labels[(y - 1) * width + x] : -1

      if (left < 0 && up < 0) {
        labels[idx] = nextLabel
        parent[nextLabel] = nextLabel
        size[nextLabel] = 1
        nextLabel++
      } else if (up < 0) {
        labels[idx] = left
        size[left]++
      } else if (left < 0) {
        labels[idx] = up
        size[up]++
      } else {
        const rootL = findRoot(parent, left)
        const rootU = findRoot(parent, up)
        if (rootL !== rootU) {
          if (size[rootL] < size[rootU]) {
            parent[rootL] = rootU
            size[rootU] += size[rootL]
            labels[idx] = rootU
          } else {
            parent[rootU] = rootL
            size[rootL] += size[rootU]
            labels[idx] = rootL
          }
        } else {
          labels[idx] = rootL
          size[rootL]++
        }
      }
    }
  }

  // Find largest component
  let largestLabel = -1
  let largestSize = 0
  for (let i = 0; i < nextLabel; i++) {
    const root = findRoot(parent, i)
    if (root === i && size[i] > largestSize) {
      largestSize = size[i]
      largestLabel = i
    }
  }

  // Pass 2: clear all but the largest component
  for (let i = 0; i < mask.length; i++) {
    if (labels[i] >= 0) {
      mask[i] = (findRoot(parent, labels[i]) === largestLabel) ? 1.0 : 0.0
    } else {
      mask[i] = 0.0
    }
  }
}

function gaussianBlurMask(mask, width, height, sigma) {
  if (sigma <= 0) return
  const radius = Math.max(1, Math.ceil(sigma * 2.5))
  const kernel = []
  let kernelSum = 0
  for (let i = -radius; i <= radius; i++) {
    const w = Math.exp(-(i * i) / (2 * sigma * sigma))
    kernel.push(w)
    kernelSum += w
  }
  for (let i = 0; i < kernel.length; i++) kernel[i] /= kernelSum

  // Horizontal pass
  const temp = new Float32Array(mask.length)
  for (let y = 0; y < height; y++) {
    for (let x = 0; x < width; x++) {
      let sum = 0
      for (let k = -radius; k <= radius; k++) {
        const nx = Math.max(0, Math.min(width - 1, x + k))
        sum += mask[y * width + nx] * kernel[k + radius]
      }
      temp[y * width + x] = sum
    }
  }

  // Vertical pass
  for (let y = 0; y < height; y++) {
    for (let x = 0; x < width; x++) {
      let sum = 0
      for (let k = -radius; k <= radius; k++) {
        const ny = Math.max(0, Math.min(height - 1, y + k))
        sum += temp[ny * width + x] * kernel[k + radius]
      }
      mask[y * width + x] = sum
    }
  }
}

// ---------- ROI绘制 ----------
function drawRois(ctx) {
  const rois = currentMeta.value?.rois || []
  ctx.save()
  ctx.lineWidth = 2
  ctx.font = '14px Microsoft YaHei, Arial'
  ctx.textBaseline = 'bottom'
  for (const roi of rois) {
    if (!roi.points?.length) continue
    if (roi.type === 'line' && roi.points.length >= 2) {
      const p1 = roi.points[0], p2 = roi.points[1]
      ctx.strokeStyle = '#ff2d55'; ctx.fillStyle = '#ff2d55'
      ctx.beginPath(); ctx.moveTo(p1.x, p1.y); ctx.lineTo(p2.x, p2.y); ctx.stroke()
      ctx.fillText(roi.name, p1.x + 6, p1.y - 4)
    } else {
      const cx = roi.points.reduce((s, p) => s + p.x, 0) / roi.points.length
      const cy = roi.points.reduce((s, p) => s + p.y, 0) / roi.points.length
      ctx.strokeStyle = '#ff2d55'; ctx.fillStyle = '#ff2d55'
      ctx.beginPath(); ctx.arc(cx, cy, 6, 0, Math.PI * 2); ctx.stroke()
      ctx.fillText(roi.name, cx + 8, cy - 6)
    }
  }
  ctx.restore()
}

// ---------- 伪彩色带（增加 medical） ----------
function pseudoColor(v, name) {
  if (name === 'gray') {
    const g = Math.round(v * 255)
    return [g, g, g]
  }
  if (name === 'iron') {
    return interpolatePalette(v, [
      [0, 0, 0], [75, 0, 130], [160, 30, 0], [255, 120, 0], [255, 230, 130], [255, 255, 255]
    ])
  }
  if (name === 'rainbow') {
    return interpolatePalette(v, [
      [30, 0, 120], [0, 0, 220], [0, 200, 255], [0, 220, 70], [255, 240, 0], [255, 80, 0], [255, 0, 160]
    ])
  }
  if (name === 'medical') {
    // 医疗色带：黑→深蓝→浅蓝→绿→黄→橙→红→白
    return interpolatePalette(v, [
      [0, 0, 0], [0, 0, 128], [0, 128, 255], [0, 255, 0], [255, 255, 0], [255, 128, 0], [255, 0, 0], [255, 255, 255]
    ])
  }
  // 默认 thermal
  return interpolatePalette(v, [
    [0, 0, 70], [0, 0, 200], [0, 200, 255], [40, 220, 80], [230, 230, 40], [255, 40, 30], [230, 0, 180]
  ])
}

function interpolatePalette(v, colors) {
  const n = colors.length - 1
  const p = v * n
  const i = Math.min(Math.floor(p), n - 1)
  const t = p - i
  const c1 = colors[i], c2 = colors[i + 1]
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
  if (name === 'medical') return 'linear-gradient(to top, #000, #000080, #0080ff, #00ff00, #ffff00, #ff8000, #ff0000, #fff)'
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
.topbar h1 { margin: 0; font-size: 24px; }
.topbar p { margin: 6px 0 0; color: #64748b; }
.patient { display: flex; gap: 14px; color: #475569; font-size: 14px; }

.workspace {
  display: grid;
  grid-template-columns: minmax(520px, 1fr) 360px;
  gap: 18px;
  align-items: start;
}
.viewer-card, .control-card {
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
.viewer-title h2, .control-card h2 { margin: 0; font-size: 20px; }
.viewer-title p { margin: 6px 0 0; color: #64748b; }
.warning { color: #dc2626 !important; }
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
.thermal-canvas { max-height: 100%; max-width: 100%; background: #fff; image-rendering: auto; }
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
.thumb.active { border-color: #2563eb; background: #eff6ff; }
.thumb img { width: 100%; height: 110px; object-fit: contain; display: block; }
.thumb span, .thumb small { display: block; }
.thumb span { font-size: 13px; margin-top: 4px; }
.thumb small { color: #64748b; }
.info-card {
  margin-top: 14px;
  background: #fff;
  border-radius: 18px;
  padding: 18px;
  box-shadow: 0 8px 24px rgba(15, 23, 42, 0.08);
  display: flex;
  gap: 18px;
}
.info-col { flex: 1; min-width: 0; }
.info-col h3 { margin: 0 0 8px; font-size: 15px; }
.info-col .roi-item { font-size: 14px; color: #475569; margin: 4px 0; }
.info-col .result-text {
  white-space: pre-wrap;
  line-height: 1.7;
  margin: 0;
  color: #475569;
  font-size: 14px;
  max-height: 200px;
  overflow-y: auto;
}
@media (max-width: 900px) {
  .info-card { flex-direction: column; }
}

.control-card { position: sticky; top: 20px; }
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
.group { margin-top: 18px; }
.inline-row { display: flex; gap: 12px; align-items: flex-start; }
.group label { display: block; font-weight: 600; margin-bottom: 8px; }
.group input[type="range"], .group select { width: 100%; }
.group select {
  height: 38px;
  border: 1px solid #cbd5e1;
  border-radius: 10px;
  padding: 0 10px;
  background: #fff;
}
.checkbox { display: flex; gap: 8px; align-items: center; }
.checkbox label { margin: 0; }
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

/* 高级增强折叠面板 */
.advanced-group {
  margin-top: 18px;
  background: #f8fafc;
  border-radius: 12px;
  padding: 12px;
  border: 1px solid #e2e8f0;
}
.advanced-group summary {
  font-size: 15px;
  cursor: pointer;
  margin-bottom: 12px;
  color: #1f2937;
}

@media (max-width: 980px) {
  .workspace { grid-template-columns: 1fr; }
  .control-card { position: static; }
}
</style>