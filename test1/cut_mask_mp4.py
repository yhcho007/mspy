import cv2
import os
from moviepy.editor import VideoFileClip, concatenate_videoclips, AudioFileClip

# ⚙️ 설정
input_path = "SSYouTube.online_학부모설명회 YM 트렉 저니 (Trek Journey) 2021_1080p.mp4"
temp_trimmed_path = "temp_trimmed.mp4"
temp_masked_video_path = "temp_masked_noaudio.mp4"
output_path = "output_masked.mp4"

# ✂️ 삭제할 시간 구간 리스트
cut_intervals = [
    (0, 10)
]

# 🎞️ 1. MoviePy로 자르기 및 오디오 포함한 영상 저장
original_clip = VideoFileClip(input_path)

keep_intervals = []
prev_end = 0
for start, end in sorted(cut_intervals):
    if prev_end < start:
        keep_intervals.append((prev_end, start))
    prev_end = max(prev_end, end)
if prev_end < original_clip.duration:
    keep_intervals.append((prev_end, original_clip.duration))

clips_to_concatenate = [original_clip.subclip(s, e) for s, e in keep_intervals]
final_clip = concatenate_videoclips(clips_to_concatenate)

# ✅ 오디오 포함해서 저장
final_clip.write_videofile(temp_trimmed_path, codec="libx264", audio_codec="aac")

# 🎨 2. OpenCV로 마스킹 (영상만 저장, 소리 없음)
cap = cv2.VideoCapture(temp_trimmed_path)
if not cap.isOpened():
    print("동영상 파일을 열 수 없습니다.")
    exit(1)

fps = cap.get(cv2.CAP_PROP_FPS)
width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

fourcc = cv2.VideoWriter_fourcc(*'mp4v')
out = cv2.VideoWriter(temp_masked_video_path, fourcc, fps, (width, height))

mask_schedule = [
    (0, 362, [
        (0, 0, 300, 53, (240, 240, 240))
    ])
]

frame_idx = 0

while True:
    ret, frame = cap.read()
    if not ret:
        break

    current_time = frame_idx / fps

    for start_time, end_time, areas in mask_schedule:
        if start_time <= current_time <= end_time:
            for x, y, w, h, color in areas:
                x_end = min(x + w, width)
                y_end = min(y + h, height)
                frame[y:y_end, x:x_end] = color

    out.write(frame)
    frame_idx += 1

cap.release()
out.release()
cv2.destroyAllWindows()

# 🔊 3. MoviePy로 마스킹된 영상에 오디오 덧붙이기
masked_clip = VideoFileClip(temp_masked_video_path)
audio_clip = final_clip.audio  # 마스킹 전 원래 오디오

final_video_with_audio = masked_clip.set_audio(audio_clip)
final_video_with_audio.write_videofile(output_path, codec="libx264", audio_codec="aac")

print(f"✅ 완료: {output_path} 에 저장되었습니다.")
