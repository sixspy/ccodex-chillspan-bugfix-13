export const lineageViewTemplate = `
<section class="panel">
  <h2>冷链血缘</h2>
  <div class="form-row">
    <div><label>来源批次ID</label><input type="number" v-model.number="lineageForm.from_batch_id"/></div>
    <div><label>目标批次ID</label><input type="number" v-model.number="lineageForm.to_batch_id"/></div>
    <div><label>类型</label><input v-model="lineageForm.edge_type"/></div>
    <div><label>说明</label><input v-model="lineageForm.detail"/></div>
  </div>
  <div class="actions"><button @click="addLineageEdge">登记血缘边</button></div>
  <table class="data-table">
    <thead><tr><th>自</th><th>至</th><th>类型</th><th>说明</th><th>时间</th></tr></thead>
    <tbody>
      <tr v-for="e in lineageEdges" :key="e.id">
        <td>{{ e.from_code }}</td>
        <td>{{ e.to_code || "—" }}</td>
        <td>{{ e.edge_type }}</td>
        <td>{{ e.detail }}</td>
        <td>{{ e.created_at }}</td>
      </tr>
    </tbody>
  </table>
  <div class="form-row">
    <div><label>批次温谱摘要查询（批次ID）</label>
      <input type="number" v-model.number="lineageSummaryBatchId"/></div>
  </div>
  <div class="actions"><button class="secondary" @click="loadLineageSummary">查血统温谱摘要</button></div>
  <div v-if="lineageSummary" class="detail-box">
    <p class="hint">正式温谱摘要（与温谱/封批/互证同源）：</p>
    <table v-if="lineageSummary.formal_exports.length" class="data-table">
      <thead><tr><th>导出号</th><th>格式</th><th>点数</th><th>校验和</th><th>校验态</th></tr></thead>
      <tbody>
        <tr v-for="x in lineageSummary.formal_exports" :key="x.export_ref">
          <td>{{ x.export_ref }}</td>
          <td>{{ x.export_format }}</td>
          <td>{{ x.point_count }}</td>
          <td class="mono">{{ x.checksum }}</td>
          <td><span class="badge pass">{{ x.checksum_state }}</span></td>
        </tr>
      </tbody>
    </table>
    <p v-else class="hint">该批无正式温谱导出（空摘要/待重算遗痕不对外）。</p>
  </div>
</section>
`;
