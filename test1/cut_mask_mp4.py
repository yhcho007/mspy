import cv2
from moviepy import VideoFileClip, concatenate_videoclips

# ⚙️ 설정
input_path = "SSYouTube.online_학부모설명회 YM 트렉 저니 (Trek Journey) 2021_1080p.mp4"
temp_trimmed_path = "temp_trimmed.mp4"
output_path = "output_masked.mp4"

# ✂️ 삭제할 시간 구간 리스트 (초 단위)
# 예: [(start1, end1), (start2, end2), ...]
'''
cut_intervals = [
    (0, 9),
    (15, 20),
    (30, 35),
]
'''
cut_intervals = [
    (0, 10)
]

# 🎞️ 1. MoviePy로 여러 구간 잘라내기 (삭제 구간 제외하고 이어붙임)
original_clip = VideoFileClip(input_path)

# 잘라내지 않고 남길 구간 리스트 생성
keep_intervals = []
prev_end = 0
for start, end in sorted(cut_intervals):
    if prev_end < start:
        keep_intervals.append((prev_end, start))
    prev_end = max(prev_end, end)
if prev_end < original_clip.duration:
    keep_intervals.append((prev_end, original_clip.duration))

# 남길 구간별로 서브클립 생성 후 연결
clips_to_concatenate = [original_clip.subclipped(s, e) for s, e in keep_intervals]
final_clip = concatenate_videoclips(clips_to_concatenate)

final_clip.write_videofile(temp_trimmed_path, codec="libx264")

# 🎨 2. OpenCV로 마스킹 작업
cap = cv2.VideoCapture(temp_trimmed_path)
if not cap.isOpened():
    print("동영상 파일을 열 수 없습니다.")
    exit(1)

fps = cap.get(cv2.CAP_PROP_FPS)
width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

fourcc = cv2.VideoWriter_fourcc(*'mp4v')
out = cv2.VideoWriter(output_path, fourcc, fps, (width, height))

# 🧱 마스킹 조건 설정
# 각 항목: (start_time_sec, end_time_sec, [ (x, y, w, h, (B,G,R)), ... ])
mask_schedule = [
    (0, 362, [
        (0, 0, 300, 53, (240, 240, 240))  # 연회색 바 영역 마스킹
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

print(f"✅ 완료: {output_path} 에 저장되었습니다.")
