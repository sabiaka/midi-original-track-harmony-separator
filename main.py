import mido

def separate_harmony_by_original_track_rank(input_midi_path, output_midi_path):
    """
    MIDIファイルの各入力トラック内の和音を検出し、その構成音を音高順のランク別に
    それぞれ新しい別の出力トラックに割り当てる関数。
    出力トラックは、入力トラック1のランク0、入力トラック1のランク1、
    入力トラック2のランク0、入力トラック2のランク1... というように連続して作成される。
    各入力トラックのノート以外のメッセージは、その入力トラックの最高音(ランク0)が
    割り当てられた新しい出力トラックに一緒に入れられる。
    もし入力トラックに音符がなくノート以外のメッセージのみの場合は、
    それらのメッセージ用に新しい専用の出力トラックが作られる。

    Args:
        input_midi_path (str): 入力MIDIファイルのパス
        output_midi_path (str): 出力MIDIファイルのパス
    """
    try:
        original_mid = mido.MidiFile(input_midi_path)
        print(f"MIDIファイル「{input_midi_path}」を読み込んだお！(๑•̀ㅂ•́)و✧")
    except FileNotFoundError:
        print(f"ありゃ、ファイル見っかんない！パス確認してちょ: {input_midi_path}")
        return
    except Exception as e:
        print(f"MIDIファイル読み込みでエラー出たっぽ！: {e}")
        return

    new_mid = mido.MidiFile(ticks_per_beat=original_mid.ticks_per_beat)
    print(f"新しいMIDIファイル作る準備おっけー！ ticks_per_beat: {new_mid.ticks_per_beat}")

    # --- ステップ1: 全ての新しい出力トラックのイベントを保存する辞書 ---
    # key: 新しい出力トラックのグローバルインデックス (0から始まる通し番号)
    # value: list of (絶対時間, MIDIメッセージ)
    all_output_events_for_new_tracks = {}
    
    # --- ステップ2: 次に割り当てる新しい出力トラックのグローバルインデックス ---
    next_global_output_track_idx_to_assign = 0

    # --- ステップ3: 各入力トラックを順番に処理 ---
    for original_track_idx, original_track_obj in enumerate(original_mid.tracks):
        print(f"--- 入力トラック {original_track_idx} の処理を開始するよん！ ---")

        # 3a. この入力トラック内のイベントを絶対時間と一緒にリスト化
        events_with_abs_time_this_orig_track = []
        current_abs_time_for_this_orig_track = 0
        for msg in original_track_obj:
            current_abs_time_for_this_orig_track += msg.time
            events_with_abs_time_this_orig_track.append({'abs_time': current_abs_time_for_this_orig_track, 'msg': msg})
        
        # イベントを絶対時間でソート (重要！)
        events_with_abs_time_this_orig_track.sort(key=lambda x: x['abs_time'])

        # 3b. この入力トラック内の時間ごとのイベントグループ
        events_grouped_by_time_this_orig_track = {}
        for event_info in events_with_abs_time_this_orig_track:
            abs_time = event_info['abs_time']
            if abs_time not in events_grouped_by_time_this_orig_track:
                events_grouped_by_time_this_orig_track[abs_time] = []
            events_grouped_by_time_this_orig_track[abs_time].append(event_info['msg']) # メッセージだけ保存

        # 3c. この入力トラック内のランクと、割り当てられたグローバル出力トラック番号のマップ
        # key: この入力トラック内の和音のランク (0が最高音), value: グローバル出力トラックidx
        rank_to_global_output_idx_map_this_orig_track = {}
        
        # 3d. この入力トラック内でアクティブなノートのピッチと、それが送られたグローバル出力トラック番号のマップ
        # key: ノートピッチ, value: グローバル出力トラックidx
        active_notes_pitch_to_global_output_idx_this_orig_track = {}
        
        # 3e. この入力トラックのノート以外のメッセージが送られるグローバル出力トラック番号
        #    （この入力トラックのランク0の音と同じところ。まだ決まってなければ-1）
        global_output_idx_for_non_notes_this_orig_track = -1

        # 3f. 時間順にイベントを処理
        sorted_abs_times_this_orig_track = sorted(events_grouped_by_time_this_orig_track.keys())

        for abs_time in sorted_abs_times_this_orig_track:
            messages_at_this_abs_time = events_grouped_by_time_this_orig_track[abs_time]
            
            current_note_ons_this_orig_track = []
            current_note_offs_this_orig_track = []
            current_other_msgs_this_orig_track = []

            for msg in messages_at_this_abs_time:
                if msg.type == 'note_on' and msg.velocity > 0:
                    current_note_ons_this_orig_track.append(msg)
                elif msg.type == 'note_off' or (msg.type == 'note_on' and msg.velocity == 0):
                    current_note_offs_this_orig_track.append(msg)
                else:
                    current_other_msgs_this_orig_track.append(msg)

            # --- ノートオフ処理 (この入力トラック内でアクティブだった音を探す) ---
            for off_msg in current_note_offs_this_orig_track:
                if off_msg.note in active_notes_pitch_to_global_output_idx_this_orig_track:
                    target_global_output_idx = active_notes_pitch_to_global_output_idx_this_orig_track[off_msg.note]
                    
                    if target_global_output_idx not in all_output_events_for_new_tracks:
                        all_output_events_for_new_tracks[target_global_output_idx] = []
                    all_output_events_for_new_tracks[target_global_output_idx].append((abs_time, off_msg.copy()))
                    
                    del active_notes_pitch_to_global_output_idx_this_orig_track[off_msg.note]
                # else:
                    # print(f"  入力trk {original_track_idx} 時刻 {abs_time}: ノートオフ {off_msg.note} の対応ノートオンが見つからんかった…")

            # --- ノートオン処理 (この入力トラック内の和音をランク分け) ---
            if current_note_ons_this_orig_track:
                # この時間・この入力トラック内のノートオンを音が高い順にソート
                sorted_note_ons_in_chord = sorted(current_note_ons_this_orig_track, key=lambda m: m.note, reverse=True)
                
                for rank_in_orig_track_chord, note_on_msg in enumerate(sorted_note_ons_in_chord):
                    # rank_in_orig_track_chord は、この入力トラックのこの和音内でのランク (0が最高音)
                    
                    target_global_output_idx_for_this_note = -1

                    # このランクの音が、この入力トラックで初めて出てきたかチェック
                    if rank_in_orig_track_chord not in rank_to_global_output_idx_map_this_orig_track:
                        # 初めてなら、新しいグローバル出力トラック番号を割り当てる
                        rank_to_global_output_idx_map_this_orig_track[rank_in_orig_track_chord] = next_global_output_track_idx_to_assign
                        
                        # もしこれがランク0の音で、まだこの入力トラックの非ノート用トラックが決まってなければ設定
                        if rank_in_orig_track_chord == 0 and global_output_idx_for_non_notes_this_orig_track == -1:
                            global_output_idx_for_non_notes_this_orig_track = next_global_output_track_idx_to_assign
                        
                        target_global_output_idx_for_this_note = next_global_output_track_idx_to_assign
                        print(f"  入力trk {original_track_idx} のランク {rank_in_orig_track_chord} の音に、新しい出力trk {target_global_output_idx_for_this_note} を割り当てたよ！")
                        next_global_output_track_idx_to_assign += 1 # グローバルカウンターを進める
                    else:
                        # このランクの音は既に出てきてるので、前に割り当てたグローバル出力トラック番号を使う
                        target_global_output_idx_for_this_note = rank_to_global_output_idx_map_this_orig_track[rank_in_orig_track_chord]

                    # リトリガー処理: 同じピッチの音がこの入力トラックで既にアクティブだったら、前の音をオフにする
                    if note_on_msg.note in active_notes_pitch_to_global_output_idx_this_orig_track:
                        previous_global_output_idx_for_this_pitch = active_notes_pitch_to_global_output_idx_this_orig_track[note_on_msg.note]
                        # print(f"  入力trk {original_track_idx} 時刻 {abs_time}: ノート {note_on_msg.note} がリトリガーっぽい。出力trk {previous_global_output_idx_for_this_pitch} の前の音をオフにするね。")
                        forced_off_msg = mido.Message('note_off', channel=note_on_msg.channel, note=note_on_msg.note, velocity=0)
                        
                        if previous_global_output_idx_for_this_pitch not in all_output_events_for_new_tracks:
                             all_output_events_for_new_tracks[previous_global_output_idx_for_this_pitch] = []
                        all_output_events_for_new_tracks[previous_global_output_idx_for_this_pitch].append((abs_time, forced_off_msg))
                        # active_notes_pitch_to_global_output_idx_this_orig_track からはノートオフ処理で消えるはずだけど、
                        # ここで消しちゃうと、同じ時間で同じピッチが別のランクで出てきた場合に困る。下で上書きするからOK。

                    # ノートオンイベントを、決定したグローバル出力トラック用のリストに追加
                    if target_global_output_idx_for_this_note not in all_output_events_for_new_tracks:
                        all_output_events_for_new_tracks[target_global_output_idx_for_this_note] = []
                    all_output_events_for_new_tracks[target_global_output_idx_for_this_note].append((abs_time, note_on_msg.copy()))
                    
                    # この入力トラックのアクティブなノート情報を更新
                    active_notes_pitch_to_global_output_idx_this_orig_track[note_on_msg.note] = target_global_output_idx_for_this_note
            
            # --- その他のメッセージ処理 (この入力トラックのランク0の音と同じ出力トラックへ) ---
            if current_other_msgs_this_orig_track:
                if global_output_idx_for_non_notes_this_orig_track == -1:
                    # この入力トラックでまだランク0の音が出てきてない (例: トラック先頭に非ノートメッセージ)
                    # なので、非ノートメッセージ用に新しいグローバル出力トラックを割り当てる
                    global_output_idx_for_non_notes_this_orig_track = next_global_output_track_idx_to_assign
                    print(f"  入力trk {original_track_idx} のノート以外のメッセージ用に、新しい出力trk {global_output_idx_for_non_notes_this_orig_track} を割り当てたよ！")
                    next_global_output_track_idx_to_assign += 1
                
                if global_output_idx_for_non_notes_this_orig_track not in all_output_events_for_new_tracks:
                    all_output_events_for_new_tracks[global_output_idx_for_non_notes_this_orig_track] = []
                for other_msg in current_other_msgs_this_orig_track:
                    all_output_events_for_new_tracks[global_output_idx_for_non_notes_this_orig_track].append((abs_time, other_msg.copy()))
        
        print(f"--- 入力トラック {original_track_idx} の処理おーわりっ！ ---")

    # --- ステップ4: 集めたイベントから新しいMIDIトラックを実際に作る ---
    num_final_output_tracks = next_global_output_track_idx_to_assign # これが実際に使われたトラック数になるはず
    
    print(f"最終的に {num_final_output_tracks} 個のトラックを作るよん！")

    for new_track_idx in range(num_final_output_tracks):
        new_midi_track_obj = mido.MidiTrack()
        new_mid.tracks.append(new_midi_track_obj)
        
        events_for_this_new_track = all_output_events_for_new_tracks.get(new_track_idx, [])
        
        if not events_for_this_new_track:
            print(f"出力トラック {new_track_idx} にはイベントなかったみたい。空っぽトラック作るね。")
        else:
            print(f"出力トラック {new_track_idx} のイベントを書き込み中... イベント数: {len(events_for_this_new_track)}")
            
            events_for_this_new_track.sort(key=lambda x: x[0]) # 絶対時間でソート
            
            last_abs_time_in_this_new_track = 0
            for abs_time, msg_to_add in events_for_this_new_track:
                delta_time = abs_time - last_abs_time_in_this_new_track
                new_midi_track_obj.append(msg_to_add.copy(time=delta_time))
                last_abs_time_in_this_new_track = abs_time
        
        # 各トラックの最後に end_of_track メタメッセージを追加 (お約束！)
        has_end_of_track = any(msg.type == 'end_of_track' for msg in new_midi_track_obj)
        if not has_end_of_track:
            time_for_eot = 0
            new_midi_track_obj.append(mido.MetaMessage('end_of_track', time=time_for_eot))

    try:
        new_mid.save(output_midi_path)
        print(f"できたー！🎉 新しいMIDIファイルはこれ見て！ → {output_midi_path}")
    except Exception as e:
        print(f"MIDIファイル保存中にエラーでちゃった💦: {e}")

# --- 使い方はここから ---
if __name__ == "__main__":
    # ↓↓↓ この2つの値を自分の環境に合わせて変えてね！ ↓↓↓
    my_input_midi_file = "unwelcome.mid"  # 入力するMIDIファイルの名前
    my_output_midi_file = "output_unwelcome_orig_track_ranked.mid" # 新しく作るMIDIファイルの名前（変えたよ！）

    # 処理スタート！
    separate_harmony_by_original_track_rank(my_input_midi_file, my_output_midi_file)
