# get_lfw_dataset.py
from sklearn.datasets import fetch_lfw_people
import cv2
import os

os.makedirs("dataset", exist_ok=True)

print("Downloading LFW dataset (this may take a minute)...")
lfw = fetch_lfw_people(min_faces_per_person=5, resize=1.0, color=True)

images = lfw.images
names = lfw.target_names
labels = lfw.target

count = 0
for i in range(len(images)):
    if count >= 100:
        break
    name = names[labels[i]].replace(" ", "_")
    person_id = f"{count+1:03d}"
    # LFW images come as float RGB 0-1, convert to BGR uint8 for cv2
    img = (images[i] * 255).astype("uint8")
    img_bgr = cv2.cvtColor(img, cv2.COLOR_RGB2BGR)
    cv2.imwrite(f"dataset/{person_id}_{name}.jpg", img_bgr)
    count += 1

print(f"Saved {count} images to dataset/")