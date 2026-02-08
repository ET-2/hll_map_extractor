import cv2 as cv
import datetime as dt
import FreeSimpleGUI as sg
import numpy
import os
import re
import time
from rapidocr import RapidOCR


class MapEngine:

	def __init__(self):
		self.CYCLE = 0
		self.MIN_MATCH_COUNT = 1000
		self.MIN_MATCH_COUNT_WARMUP = 30
		self.IN_GAME_CLOCK = dt.time()
		self.SANITY_CHECK_CLOCK = dt.time()
		self.CLOCK_SET = False
		self.FRAME_COUNT = 0
		self.input_path = ''
		self.map_path = ''
		self.window = ''

		# loading images
		self.map_example = ''
		self.warmup_example = cv.imread('assets/warmup.png', cv.IMREAD_GRAYSCALE)

		self.layout = [
			[
				sg.Text('Select Map:', pad=(10, 10)),
				sg.Combo((
					'CARENTAN',
					'DRIEL',
					'EL_ALAMEIN',
					'ELSENBORN',
					'FOY',
					'HILL_400',
					'HURTGEN',
					'KHARKOV',
					'KURSK',
					'MORTAIN',
					'OMAHA',
					'PHL',
					'REMAGEN',
					'SMDM',
					'SME',
					'SMOLENSK',
					'STALINGRAD',
					'TOBRUK',
					'UTAH'),
				size=(25,19),
				readonly=True,
				key='maps')
			],
			[sg.Text('Selected File:', pad=(10, 10)), sg.FileBrowse(button_text='Browse')],
			[sg.Button('Start'), sg.Button('Quit'), sg.Text('Cycle: 0', key='-OUTPUT-'+sg.WRITE_ONLY_KEY)],
			[sg.MLine(size=(65,20), autoscroll=True, write_only=True, key='-WINDOW-'+sg.WRITE_ONLY_KEY)],
		]


	def _sanity_check(self):
		# Make sure clock was not set before map flip
		if self.CLOCK_SET:
			if self.IN_GAME_CLOCK > self.SANITY_CHECK_CLOCK:
				self.CLOCK_SET = False


	def _flann(self, frame, des, sift):
		_, des2 = sift.detectAndCompute(frame, None)
		index_params = dict(algorithm=1, trees=5)
		search_params = dict(checks=50)
		flann = cv.FlannBasedMatcher(index_params, search_params)
		matches = flann.knnMatch(des, des2, k=2)

		return matches


	def set_input(self, target_map, input_path):
		target_map = f'assets/{target_map}.png'
		self.map_example = cv.imread(target_map, cv.IMREAD_GRAYSCALE)
		self.input_path = input_path


	def add_timestamp(self, frame):
		clock = f'{self.IN_GAME_CLOCK.hour}:{"{:0>2}".format(self.IN_GAME_CLOCK.minute)}:{"{:0>2}".format(self.IN_GAME_CLOCK.second)}'
		frame = cv.putText(frame, clock, (100, 60), cv.FONT_HERSHEY_COMPLEX, 2, (255, 255, 255), 5)

		return frame 


	def check_clock(self, des, sift, frame):
		matches = self._flann(frame, des, sift)
		good = []
		for m,n in matches:
			if m.distance < 0.75*n.distance:
				good.append(m)

		if len(good) > self.MIN_MATCH_COUNT_WARMUP:
			text = self.get_text(frame)

			# Check for match warmup clock
			if 'MATCH WARMUP' in text:
				index = text.index('MATCH WARMUP') + 1
				time = text[index].split(':', maxsplit=1)
				wm_minute, wm_second = time[0], time[1]

				self.IN_GAME_CLOCK = dt.time(hour=1, minute=27+int(wm_minute), second=int(wm_second))
				self.SANITY_CHECK_CLOCK = self.IN_GAME_CLOCK
				self.window['-WINDOW-'+sg.WRITE_ONLY_KEY].print(f'Clock set @ {self.IN_GAME_CLOCK.hour}:{"{:0>2}".format(self.IN_GAME_CLOCK.minute)}:{"{:0>2}".format(self.IN_GAME_CLOCK.second)}')
				self.CLOCK_SET = True

		elif self.CYCLE % 5 == 0: 
			text = self.get_text(frame)

			# Check for toggled clock or spawn screen clock
			try:
				for item in text:
					if re.match('\\d{1}:\\d{2}:\\d{2}', item):
						ret = item.split(':', maxsplit=2)
						wm_hour, wm_minute, wm_second = ret[0], ret[1], ret[2]

						self.IN_GAME_CLOCK = dt.time(hour=int(wm_hour), minute=int(wm_minute), second=int(wm_second))
						self.SANITY_CHECK_CLOCK = self. IN_GAME_CLOCK
						self.window['-WINDOW-'+sg.WRITE_ONLY_KEY].print(f'Clock set @ {self.IN_GAME_CLOCK.hour}:{"{:0>2}".format(self.IN_GAME_CLOCK.minute)}:{"{:0>2}".format(self.IN_GAME_CLOCK.second)}')
						self.CLOCK_SET = True
			except:
				self.window['-WINDOW-'+sg.WRITE_ONLY_KEY].print('Clock Check Failed...Passing')
				self.window['-WINDOW-'+sg.WRITE_ONLY_KEY].print()
				pass


	def check_frame(self, des, sift, masked, video, frame):
		self.window['-OUTPUT-'+sg.WRITE_ONLY_KEY].update(f'Cycle: {self.CYCLE}')
		matches = self._flann(masked, des, sift)
		good = []
		for m,n in matches:
			if m.distance < 0.75*n.distance:
				good.append(m)

		# Write frame to video if map is on screen
		if len(good) > self.MIN_MATCH_COUNT:
			if self.CLOCK_SET:
				frame = self.add_timestamp(frame)

			video.write(frame)
			self.window['-WINDOW-'+sg.WRITE_ONLY_KEY].print(f'Added Frame: {self.FRAME_COUNT} @ {self.IN_GAME_CLOCK.hour}:{'{:0>2}'.format(self.IN_GAME_CLOCK.minute)}:{'{:0>2}'.format(self.IN_GAME_CLOCK.second)}')
			self.FRAME_COUNT += 1


	def get_text(self, frame):
		ocr = RapidOCR()
		text = ocr(frame).txts

		return text


	def gui(self):
		# Launch Window
		self.window = sg.Window('HLL Map Extractor', self.layout)

		while True:
			event, values = self.window.read()

			if event == 'Quit' or event == sg.WIN_CLOSED:
				break
			if event == 'Start':
				if values['maps'] == '' and values['Browse'] != '':
					self.window['-WINDOW-'+sg.WRITE_ONLY_KEY].print('NO MAP SELECTED', colors='red')

				if values['maps'] != '' and values['Browse'] == '':
					self.window['-WINDOW-'+sg.WRITE_ONLY_KEY].print('NO FILE SELECTED', colors='red')

				if values['maps'] == '' and values['Browse'] == '':
					self.window['-WINDOW-'+sg.WRITE_ONLY_KEY].print('NO MAP OR FILE SELECTED', colors='red')

				# Exit loop once map and file are chosen
				if values['maps'] != '' and values['Browse'] != '':
					target_map = values['maps']
					vod_path = values['Browse']
					self.set_input(target_map, vod_path)
					self.run()
					

	def run(self):
		# Begin extraction process
		self.window['-WINDOW-'+sg.WRITE_ONLY_KEY].print('Process Starting...', colors='green')

		cap = cv.VideoCapture(self.input_path)
		if not cap.isOpened():
			self.window['-WINDOW-'+sg.WRITE_ONLY_KEY].print(f'Failed to open video at {self.input_path}', colors='red')
			exit()

		# Get input video properties
		frame_width = int(cap.get(cv.CAP_PROP_FRAME_WIDTH))
		frame_height = int(cap.get(cv.CAP_PROP_FRAME_HEIGHT))
		template_h, template_w = self.map_example.shape[:2]
		padding_width = int((frame_width - template_w) // 2)
		padding_height = int((frame_height - template_h) // 2)
		mask_top_left = (padding_width, padding_height)
		mask_bottom_right = ((padding_width + template_w), (padding_height + template_h))
		offset = 500

		# Establish video params
		fourcc = cv.VideoWriter_fourcc(*'mp4v')
		video = cv.VideoWriter('output.mp4', fourcc, 4, (frame_width, frame_height), isColor=True)

		# Load sifting plates
		sift = cv.SIFT_create()
		_, loaded_map = sift.detectAndCompute(self.map_example, None)
		_, warmup_snippet = sift.detectAndCompute(self.warmup_example, None)

		# Iterate through video frame by frame
		while True:
			ret, frame = cap.read()

			# Break the loop if the video ends
			if not ret:
				break

			gray_frame = cv.cvtColor(frame, cv.COLOR_BGR2GRAY)

			# Check if clock time has been found yet
			if not self.CLOCK_SET:
				self.check_clock(warmup_snippet, sift, gray_frame)

			# Apply mask to frame
			rows, cols = gray_frame.shape[:2]
			mask = numpy.zeros((rows, cols), dtype=numpy.uint8)
			cv.rectangle(mask, mask_top_left, mask_bottom_right, 255, -1)
			masked = cv.bitwise_and(frame, frame, mask=mask)

			# Check if frame contains a map
			self.check_frame(loaded_map, sift, masked, video, frame)

			# Skip ahead half a second so we don't go frame by frame
			cap.set(cv.CAP_PROP_POS_MSEC, offset)
			offset += 500

			# Math to keep timestamp in sync with in game clock
			if self.CYCLE % 2 == 0:
				temp = dt.datetime.combine(dt.datetime(2001, 9, 11, 0, 0), self.IN_GAME_CLOCK)
				temp -= dt.timedelta(seconds=1)
				self.IN_GAME_CLOCK = temp.time()

			# Sanity check (1 minute interval)
			if self.CYCLE % 120 == 0:
				self._sanity_check()

			self.CYCLE += 1
			self.window.refresh()

		# Release the video capture object
		cap.release()
		video.release()
		cv.destroyAllWindows()

		self.window['-WINDOW-'+sg.WRITE_ONLY_KEY].print('')
		self.window['-WINDOW-'+sg.WRITE_ONLY_KEY].print(f'Process Completed with {self.FRAME_COUNT} frames @ {os.getcwd()}\\output.mp4')
		self.window.refresh()


if __name__ == '__main__':
	engine = MapEngine()
	engine.gui()
