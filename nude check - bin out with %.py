import os
import cv2
import numpy as np
import onnxruntime

__labels = [
    "FEMALE_GENITALIA_COVERED",
    "FACE_FEMALE",
    "BUTTOCKS_EXPOSED",
    "FEMALE_BREAST_EXPOSED",
    "FEMALE_GENITALIA_EXPOSED",
    "MALE_BREAST_EXPOSED",
    "ANUS_EXPOSED",
    "FEET_EXPOSED",
    "BELLY_COVERED",
    "FEET_COVERED",
    "ARMPITS_COVERED",
    "ARMPITS_EXPOSED",
    "FACE_MALE",
    "BELLY_EXPOSED",
    "MALE_GENITALIA_EXPOSED",
    "ANUS_COVERED",
    "FEMALE_BREAST_COVERED",
    "BUTTOCKS_COVERED",
]

def _read_image(image_path, target_size=320):
    # From ultralytics
    img = cv2.imread(image_path)
    img_height, img_width = img.shape[:2]
    img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)

    # Calculate the aspect ratio
    aspect = img_width / img_height

    if img_height > img_width:
        new_height = target_size
        new_width = int(target_size * aspect)
    else:
        new_width = target_size
        new_height = int(target_size / aspect)

    # Resize the image preserving aspect ratio
    img = cv2.resize(img, (new_width, new_height))

    # Pad the shorter side to make the image square
    pad_x = target_size - new_width  # Width padding
    pad_y = target_size - new_height  # height padding

    img = np.pad(
        img,
        ((pad_y // 2, pad_y - pad_y // 2), (pad_x // 2, pad_x - pad_x // 2), (0, 0)),
        mode="edge",
    )

    image_data = np.array(img) / 255.0
    image_data = np.transpose(image_data, (2, 0, 1))
    image_data = np.expand_dims(image_data, axis=0).astype(np.float32)

    return image_data, img_width, img_height

def _postprocess(output, img_width, img_height, input_width, input_height):
    outputs = np.transpose(np.squeeze(output[0]))
    rows = outputs.shape[0]
    boxes = []
    scores = []
    class_ids = []
    x_factor = img_width / input_width
    y_factor = img_height / input_height

    for i in range(rows):
        classes_scores = outputs[i][4:]
        max_score = np.amax(classes_scores)

        if max_score >= 0.2:
            class_id = np.argmax(classes_scores)
            x, y, w, h = outputs[i][0], outputs[i][1], outputs[i][2], outputs[i][3]
            left = int((x - w / 2) * x_factor)
            top = int((y - h / 2) * y_factor)
            width = int(w * x_factor)
            height = int(h * y_factor)
            class_ids.append(class_id)
            scores.append(max_score)
            boxes.append([left, top, width, height])

    indices = cv2.dnn.NMSBoxes(boxes, scores, 0.25, 0.45)

    detections = []
    for i in indices:
        box = boxes[i]
        score = scores[i]
        class_id = class_ids[i]
        detections.append(
            {"class": __labels[class_id], "score": float(score), "box": box}
        )

    return detections

class NudeDetector:
    def __init__(self):
        model_file_path = os.path.join(os.path.dirname(__file__), "best.onnx")
        if not os.path.exists(model_file_path):
            raise FileNotFoundError(f"Model file not found: {model_file_path}")
        self.onnx_session = onnxruntime.InferenceSession(
            model_file_path,
            providers=["CPUExecutionProvider"],
        )
        model_inputs = self.onnx_session.get_inputs()
        input_shape = model_inputs[0].shape
        self.input_width = input_shape[2]  # 320
        self.input_height = input_shape[3]  # 320
        self.input_name = model_inputs[0].name

    def detect(self, image_path):
        preprocessed_image, image_width, image_height = _read_image(
            image_path, self.input_width
        )
        outputs = self.onnx_session.run(None, {self.input_name: preprocessed_image})
        
        # Initialize counts for explicit content and total detections
        total_detections = 0
        explicit_content_count = 0
        explicit_content_labels = []

        for output in outputs:
            detections = _postprocess(
                output, image_width, image_height, self.input_width, self.input_height
            )

            for detection in detections:
                class_label = detection["class"]
                if class_label != "FACE_FEMALE":
                    explicit_content_labels.append(class_label)
                    explicit_content_count += 1
                total_detections += 1

        # Calculate the percentage of nudity
        if total_detections > 0:
            nudity_percentage = (explicit_content_count / total_detections) * 100
        else:
            nudity_percentage = 0.0

        return {
            "nudity_percentage": nudity_percentage,
            "explicit_content_labels": explicit_content_labels
        }

if __name__ == "__main__":
    detector = NudeDetector()
    image_path = input("Enter the file location: ")
    print(f"Detecting nudity in image: {image_path}")
    result = detector.detect(image_path)

    print(f"Nudity Percentage: {result['nudity_percentage']:.2f}%")
    print("Explicit Content Labels:")
    for label in result["explicit_content_labels"]:
        print(label)

    if result['nudity_percentage'] > 0:
        print("This image has explicit content.")
    else:
        print("This image does not have any explicit content.")
