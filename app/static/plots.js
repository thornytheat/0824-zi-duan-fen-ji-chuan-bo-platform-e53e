import {element} from './client.js';

const dayReason = {
  READY: '可签',
  LABEL_TOO_LOW: '等级偏高',
  APPROVAL_OVERLAP: '审批重叠',
};

export function visualize(report,selected) {
  const target=document.querySelector('#visual');
  target.replaceChildren();
  const selectedCase=report.cases?.find(row=>row.case===selected);
  const measurement=selectedCase?.measure;
  if (!measurement) {block(target,'chart-note','选择有计算值的分组');return;}
  const e=measurement.evidence;

  const wires=block(target,'grade-wires');
  for(const [field,grade] of Object.entries(e.grades)) {
    const row=block(wires,'grade-wire'); block(row,'field-key',`字段 ${field}`);
    for(let n=0;n<=3;n++) block(row,n===grade?'grade-node active':'grade-node',`${n} 级`);
    if(e.approved.includes(Number(field))) block(row,'permit','已批准');
  }

  const days=selectedCase?.schedule?.days || measurement.schedule?.days || e.days || [];
  if (days.length) {
    const signable=days.filter(day=>day.signable).length;
    const calendar=block(target,'week-calendar');
    calendar.id='schedule';
    calendar.dataset.testid='weekly-schedule';
    const head=block(calendar,'week-head');
    block(head,'week-title','未来一周标签');
    block(head,'week-summary',`可签 ${signable} 天 · 暂缓 ${days.length-signable} 天`);
    const grid=block(calendar,'week-grid');
    grid.setAttribute('role','list');
    grid.setAttribute('aria-label','每日签发结论');
    for (const day of days) {
      const status=day.code || day.status;
      const classes=['schedule-day', day.signable ? 'is-signable' : 'is-held'];
      if (day.overlap || status==='APPROVAL_OVERLAP') classes.push('is-overlap');
      const card=element('div',null,{
        class:classes.join(' '),
        id:`schedule-day-${day.day}`,
        'data-day':day.day,
        'data-signable':String(Boolean(day.signable)),
        'data-status':status,
        'data-testid':'schedule-day',
        role:'listitem',
      });
      block(card,'schedule-day-number',`第 ${day.day} 天`);
      block(card,'schedule-grade',`${day.label ?? day.grade ?? day.value} 级标签`);
      block(card,day.signable?'schedule-decision signable':'schedule-decision held',
        day.signable ? '可签' : (day.overlap ? '重叠暂缓' : '暂缓'));
      if (!day.signable) block(card,'schedule-reason',dayReason[status] || status);
      grid.append(card);
    }
  }
}

function block(target,className,content) {
  const node=element('div',content,{class:className});
  target.append(node);
  return node;
}
