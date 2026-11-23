export const reconcileViewTemplate = `
<section class="panel">
  <h2>仓间对账互证</h2>
  <div class="form-row">
    <div><label>仓间编码</label><input v-model="reconCode"/></div>
    <div><label>批次互证编码</label><input v-model="proofCode"/></div>
  </div>
  <div class="actions">
    <button @click="loadRecon">对账单仓</button>
    <button class="secondary" @click="loadProof">批次互证</button>
    <button class="secondary" @click="loadReconAll">全仓对账</button>
  </div>
  <div v-if="reconOne" class="detail-box">
    <p>配额 {{ reconOne.quota_batches }} · 在批 {{ reconOne.active_batches }} · <span :class="reconOne.balanced ? 'ok' : 'bad'">{{ reconOne.balanced ? "平衡" : "失衡" }}</span></p>
  </div>
  <div v-if="proofOne" class="detail-box">
    <p>状态 {{ proofOne.status }} · 开放游标 {{ proofOne.open_excursions }} · 正式温谱 {{ proofOne.spectrum_exports }} · <span :class="proofOne.spectrum_matches_seal ? 'ok' : 'bad'">{{ proofOne.spectrum_matches_seal ? "互证一致" : "互证不齐（空摘要遗痕不计）" }}</span></p>
    <table v-if="proofOne.formal_exports && proofOne.formal_exports.length" class="data-table">
      <thead><tr><th>导出号</th><th>格式</th><th>点数</th><th>校验和</th><th>校验态</th></tr></thead>
      <tbody>
        <tr v-for="x in proofOne.formal_exports" :key="x.export_ref">
          <td>{{ x.export_ref }}</td>
          <td>{{ x.export_format }}</td>
          <td>{{ x.point_count }}</td>
          <td class="mono">{{ x.checksum }}</td>
          <td><span class="badge pass">{{ x.checksum_state }}</span></td>
        </tr>
      </tbody>
    </table>
  </div>
  <table class="data-table">
    <thead><tr><th>仓间</th><th>区域</th><th>在批</th><th>余配额</th><th>平衡</th></tr></thead>
    <tbody>
      <tr v-for="r in reconAllItems" :key="r.chamber_code">
        <td>{{ r.chamber_code }}</td>
        <td>{{ r.region }}</td>
        <td>{{ r.active_batches }}</td>
        <td>{{ r.quota_left }}</td>
        <td>{{ r.balanced ? "是" : "否" }}</td>
      </tr>
    </tbody>
  </table>
</section>
`;