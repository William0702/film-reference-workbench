# AIπ 拉片数据格式 v1

文件根字段 `schema` 为 `aipi.film-study/v1`。所有时长使用秒，保留数值精度；显示时才格式化。

`source` 保存 file、duration、width、height、fps、frameCount、hasAudio、timing。探测器还可提供逐帧 frameTimes、timeOrigin 和 sha256。帧索引从0开始，镜头出点不包含该帧。可变帧率使用实际时间，不把平均fps当成每帧恒定间隔。

`videoDuration` 是视频帧覆盖的时长；`duration` 还包含可能更长的音轨尾部。`frameTimes` 保存归一化后的N+1个边界，N为frameCount；`timeOrigin`记录源视频起始PTS。声音晚于最后视频帧结束时，末尾语言仍归入最后镜头，不能为了对齐画面丢弃尾音。

每个 `shots` 条目包括：

| 字段 | 含义 |
|---|---|
| id | 连续镜号，如S01；文件名和语言引用依此关联。 |
| start、end | 镜头相对于素材播放起点的时间。 |
| startFrame、endFrame | 原片帧索引；出点为下一镜第一帧或全片帧数。 |
| size、camera、transition | 景别、运镜和入镜转场，用清楚的文字。 |
| description、subjects | 画面事实、出场人物名字。 |
| frames.in、frames.out | 可访问的参考帧路径，相对结果数据文件。 |
| dialogueIds | 独立语言时间表中与本镜有实际重叠的事件。 |
| sound.status、sound.note | pending、reviewed或non-speech，以及实际核对依据。 |
| director | intention人物意图、emotion情绪变化、blocking视线空间、edit切镜理由、reshoot复拍建议。 |
| evidence | 画面和声音判断的具体依据或疑点。 |

`dialogue` 独立于镜头保存 id、start、end、speaker、text、type、source、status、rawSubtitle、notes。`verified`只代表该source已经核实；source=subtitle的核实不等于音轨听写完成。type可区分对白、画外音、唱腔和subtitle-meaning。后者表示源字幕提供的释义。

跨镜语言在各相关镜头完整引用，而独立SRT每个语言事件仅输出一次。微秒级数值误差不能制造假重复，求区间交集时允许1微秒容差。

`review.audio.state` 使用not-reviewed、partial或complete；`coverage`保存检查区间、method、notes及实际完成的audioChecked/subtitlesChecked。`openIssues`逐项记录未解决内容。只有真实逐段审核后才能写完成；无语音也要有听审依据，不能把识别无结果改成non-speech。

有音轨时，完成审核的coverage必须以`audioChecked: true`覆盖整个素材时长；只核对字幕不能填此标志。某镜确认没有语言时，另以覆盖整镜的区间记录`result: "non-speech"`及具体notes，并将该镜sound.status设为non-speech。此标志是对实际核对结果的记录，不能由识别空结果自动生成。

`review.visual`可记录画面审核状态与范围。检测底稿允许尚未补全的内容；完整生产检查应拒绝缺失的画面事实、未审核声音、未解决语言或遗漏引用。
