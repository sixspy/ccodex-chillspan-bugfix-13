export const spectrumViewTemplate = `
<section class="panel">
  <h2>温谱导出</h2>
  <p class="hint">仅已封批批次可导出；同代同格式重复导出将被拒绝。格式切换与校验和同事务重算绑定，空摘要零增拒发，不存在影子稿对外。</p>
  <div class="form-row">
    <div><label>已封批批次</label>
      <select v-model.number="spectrumForm.batch_id"><option v-for="b in sealedBatches" :key="b.id" :value="b.id">{{ b.batch_code }} G{{ b.generation }}</option></select>
    </div>
    <div><label>导出格式（封口白名单）</label>
      <select v-model="spectrumForm.export_format">
        <option value="json">JSON</option>
        <option value="csv">CSV</option>
      </select>
    </div>
  </div>
  <div class="actions"><button @click="doSpectrum">导出温谱</button></div>
  <table class="data-table">
    <thead><tr><th>导出号</th><th>批次</th><th>格式</th><th>点数</th><th>校验和</th><th>校验态</th><th>正式下发</th><th>状态</th></tr></thead>
    <tbody>
      <tr v-for="x in spectrumExports" :key="x.id">
        <td>{{ x.export_ref }}</td>
        <td>{{ x.batch_code }}</td>
        <td>{{ x.export_format }}</td>
        <td>{{ x.point_count }}</td>
        <td class="mono">{{ x.checksum || "—" }}</td>
        <td><span class="badge" :class="x.checksum === '' ? 'fail' : 'pass'">{{ x.checksum_state || "已重算" }}</span></td>
        <td><span class="badge" :class="x.formally_issued ? 'pass' : 'frozen'">{{ x.formally_issued ? "是" : "否（待重算遗痕）" }}</span></td>
        <td><span class="badge" :class="x.formally_issued ? 'pass' : 'fail'">{{ x.status }}</span></td>
      </tr>
    </tbody>
  </table>
</section>
`;
