export const sealViewTemplate = `
<section class="panel">
  <h2>封批升代</h2>
  <p class="hint">校准有效且无开放游标时方可封批。封口纪要含格式摘要绑定口径：格式切换须同事务重算写回，空摘要零增拒发。</p>
  <div class="form-row">
    <div><label>批次</label>
      <select v-model.number="sealForm.batch_id"><option v-for="b in sealableBatches" :key="b.id" :value="b.id">{{ b.batch_code }}</option></select>
    </div>
    <div><label>快照附言</label><input v-model="sealForm.manifest"/></div>
  </div>
  <div class="actions"><button @click="doSeal">执行封批</button></div>
  <table class="data-table">
    <thead><tr><th>批次</th><th>代</th><th>封批时间</th><th>封口纪要（校验和绑定）</th><th>正式温谱摘要</th></tr></thead>
    <tbody>
      <tr v-for="s in seals" :key="s.id">
        <td>{{ s.batch_code }}</td>
        <td>{{ s.batch_generation }}</td>
        <td>{{ s.sealed_at }}</td>
        <td>{{ sealManifestNote(s.manifest) }}</td>
        <td><span class="mono">{{ formalSpectrumNote(s.batch_id) }}</span></td>
      </tr>
    </tbody>
  </table>
</section>
`;
