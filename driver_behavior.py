# Copyright (c) Microsoft. All rights reserved.
# Licensed under the MIT license. See LICENSE file in the project root for
# full license information.

import numpy as np
import dlib
from cv2 import cv2 as cv

class BehaviorClass():
    def __init__(self):

        # Initialize drowsiness and yawn checking
        self.detector = dlib.get_frontal_face_detector()
        self.predictor = dlib.shape_predictor("models/emotion_ferplus/shape_predictor_68_face_landmarks.dat")
        self.eye_threshold = 0.18
        self.mouth_threshold = 0.2
        self.face_size_w = 400
        self.face_size_h = 400
        self.frame = None

    def eye_aspect_ratio(self, eye):
        # calculate the distances between the two sets of vertical eye landmarks
        A = np.sqrt((eye[1][0] - eye[5][0]) ** 2 + (eye[1][1] - eye[5][1]) ** 2)
        B = np.sqrt((eye[2][0] - eye[4][0]) ** 2 + (eye[2][1] - eye[4][1]) ** 2)
     
        # calculate the distance between the horizontal eye landmark   
        C = np.sqrt((eye[0][0] - eye[3][0]) ** 2 + (eye[0][1] - eye[3][1]) ** 2)
     
        # calculate the eye aspect ratio
        ear = (A + B) / (2.0 * C)

        return ear

    def get_gaze_ratio(self, lmk):
        eye_region = np.array([(lmk[0].x, lmk[0].y),
                                (lmk[1].x, lmk[1].y),
                                (lmk[2].x, lmk[2].y),
                                (lmk[3].x, lmk[3].y),
                                (lmk[4].x, lmk[4].y),
                                (lmk[5].x, lmk[5].y)], np.int32)
        # cv.polylines(frame, [eye_region], True, (0, 0, 255), 2)
        height, width, _ = self.frame.shape
        mask = np.zeros((height, width), np.uint8)
        cv.polylines(mask, [eye_region], True, 255, 2)
        cv.fillPoly(mask, [eye_region], 255)

        gray = cv.cvtColor(self.frame, cv.COLOR_BGR2GRAY)
        eye = cv.bitwise_and(gray, gray, mask=mask)

        min_x = np.min(eye_region[:, 0])
        max_x = np.max(eye_region[:, 0])
        min_y = np.min(eye_region[:, 1])
        max_y = np.max(eye_region[:, 1])

        gray_eye = eye[min_y: max_y, min_x: max_x]
        _, threshold_eye = cv.threshold(gray_eye, 40, 255, cv.THRESH_BINARY)
        h, w = threshold_eye.shape

        left_side_threshold = threshold_eye[0: h, 0: int(w / 2)]
        left_side_white = cv.countNonZero(left_side_threshold)

        right_side_threshold = threshold_eye[0: h, int(w / 2): w]
        right_side_white = cv.countNonZero(right_side_threshold)

        # print('left white:', left_side_white)
        # print('right white:', right_side_white)

        if left_side_white == 0 and right_side_white == 0:
            gaze_ratio = 1
        elif left_side_white == 0:
            gaze_ratio = 0.1
        elif right_side_white == 0:
            gaze_ratio = 10
        else:
            gaze_ratio = left_side_white / right_side_white
        return gaze_ratio

    def check_drowsiness_yawn(self, img, rect, dtype="int"):
        self.frame = img

        img = img[:, :, [2, 1, 0]]  # BGR => RGB
        yawn = False
        drowsiness = False

        landmarks = self.predictor(img, rect)

		# get the left and right eye coordinates
        left_eye = []
        for i in range(36, 42):
            left_eye.append([landmarks.part(i).x, landmarks.part(i).y])
        right_eye = []
        for i in range(42, 48):
            right_eye.append([landmarks.part(i).x, landmarks.part(i).y])

        # calculate the eye aspect ratio for both eyes
        left_ear = self.eye_aspect_ratio(left_eye)
        right_ear = self.eye_aspect_ratio(right_eye)
 
        # average the eye aspect ratio together for both eyes
        ear = (left_ear + right_ear) / 2.0
            
        # check to see if the eye aspect ratio is below the eye threshold
        if ear < self.eye_threshold:
            drowsiness = True

        # check yawn
        top_lips=[]
        bottom_lips=[]
        for i in range(0, 68):        
            if 50 <= i <= 53 or 61 <= i <= 64:
                top_lips.append((landmarks.part(i).x, landmarks.part(i).y))
        
            elif 65 <= i <= 68 or 56 <= i <= 59:
                bottom_lips.append((landmarks.part(i).x, landmarks.part(i).y))

        top_lips = np.squeeze(np.asarray(top_lips))
        bottom_lips = np.squeeze(np.asarray(bottom_lips))
        top_lips_mean=np.array(np.mean(top_lips, axis = 0), dtype=dtype)
        bottom_lips_mean = np.array(np.mean(bottom_lips, axis=0), dtype=dtype)
        top_lips_mean = top_lips_mean.reshape(-1) 
        bottom_lips_mean = bottom_lips_mean.reshape(-1) 
        
        #distance=math.sqrt((bottom_lips_mean[0] - top_lips_mean[0])**2 + (bottom_lips_mean[-1] - top_lips_mean[-1])**2)
        distance = bottom_lips_mean[-1] - top_lips_mean[-1]

        threshold = (rect.bottom() - rect.top()) * self.mouth_threshold     
        if distance > threshold:
            yawn=True

        # gaze detection
        left_gaze_ratio = self.get_gaze_ratio([landmarks.part(i) for i in range(36, 42)])
        right_gaze_ratio = self.get_gaze_ratio([landmarks.part(i) for i in range(42, 48)])
        gaze_ratio = (right_gaze_ratio + left_gaze_ratio) / 2

        if gaze_ratio <= 0.75:
            gaze = 'RIGHT'
        elif 0.75 < gaze_ratio < 1.3:
            gaze = 'CENTER'
        else:
            gaze = 'LEFT'


        return drowsiness, yawn, gaze