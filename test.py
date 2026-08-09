import cv2
import urllib.request
from insightface.app import FaceAnalysis

# download a sample test image if you don't have one
urllib.request.urlretrieve(
    'https://raw.githubusercontent.com/deepinsight/insightface/master/python-package/insightface/data/images/t1.jpg',
    'test_face.jpg'
)

app = FaceAnalysis(name='buffalo_l', providers=['CPUExecutionProvider'])
app.prepare(ctx_id=0, det_size=(640, 640))

img = cv2.imread('test_face.jpg')
faces = app.get(img)

print('Number of faces found:', len(faces))
if len(faces) > 0:
    print('Embedding shape:', faces[0].embedding.shape)
    print('Embedding dtype:', faces[0].embedding.dtype)
    print('Detection confidence:', faces[0].det_score)