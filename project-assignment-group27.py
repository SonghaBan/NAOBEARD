
from naoqi import ALProxy
import qi
import stk.services
import time
import argparse
import traceback
from gestures import *
import os
import numpy as np
cur_d = os.path.dirname(__file__)
join = os.path.join

qiapp = None

S_DURATION = 0.3
INTERVAL = 0.7

# =============================================================================
# robot class
# =============================================================================
class NaoRobot():
    
    def __init__(self,ip,port):
        self.qiapp = qi.Application(url="tcp://"+ip+":" + port)
        self.qiapp.start()
        self.s = stk.services.ServiceCache(self.qiapp.session)
        # Prepare the robot
        self.s.ALRobotPosture.goToPosture("Stand", 0.5)
        self.s.ALMotion.setBreathEnabled("Body", True)
        self.s.ALAnimatedSpeech.setBodyLanguageMode(0) 

    def parse_story(self,data):
        '''
        parse the annotated story and perform gestures
        args
        - data (str): annotated story
        '''
        opentag = dict() #to save ongoing gesture tags
        chunk = ''  #to save words to utter
        tmpgestures = [] #to temporarily save nested gestures
        startn = 0 #to check position of the nested gesture
        

        data = data.split('<') #find the starts of the tags
        
        for d in data:
            d = d.strip()
            if not d:
                continue
            tmp = d.split('>')
            tags = tmp[0].split()
            if tmpgestures:
                startn = max(1,syllable(chunk))
            chunk += ' '+tmp[1]
            
            category = tags[0]

            #if faced closing tags
            if category.startswith('/'):
                category = category.lstrip('/')
                try:
                    #if it is the biggest tag (not a nested one)
                    if len(opentag) == 1:
                        # get joints of the gesture
                        names, times, keys = globals()[opentag[category]]()

                        #if it has some nested gestures
                        if startn: 
                            fnames, ftimes, fkeys = [],[],[]
                            #prepare the main gesture first
                            for i,name in enumerate(names):
                                fnames.append(name)
                                ftimes.append(times[i])
                                fkeys.append(keys[i])
                            #for each nested gesture
                            for tmpgesture in tmpgestures:
                                startn = S_DURATION * startn #check the starting point
                                tmpgesture[1] = (np.array(tmpgesture[1]) + startn).tolist()
                                for i,name in enumerate(tmpgesture[0]):
                                    if name in fnames:
                                        continue
                                    #add joints to the final version
                                    fnames.append(name)
                                    ftimes.append(tmpgesture[1][i])
                                    fkeys.append(tmpgesture[2][i])
                            tmpgestures = []
                        else:
                            fnames, ftimes, fkeys = names, times, keys

                        print(chunk)
                        self.execute_gesture(names,times,keys,chunk) #perform the gesture
                        startn = 0
                        chunk = ''
                    #if it is a nested gesture
                    else:
                        names, times, keys = globals()[opentag[category]]()
                        tmpgestures.append([names,times,keys]) #save it in the tmp gestures and move on
                        print('tmp')
                        
                    del opentag[category]#close the gesture tag
                    
                except:
                    print(traceback.format_exc())
                    print('no gesture to finish')
                    return
                continue

            body = tags[1]
            mean = tags[2]
            
            gesture = '{}_{}_{}'.format(category,body,mean).replace('-','')

            opentag[category] = gesture

    def execute_gesture(self,names,times,keys,sentence):
        start = time.time()
        
        n_syllable = syllable(sentence)
        duration = np.max(times)
        duration = max(duration) if type(duration) != np.float64 else duration
        duration += 1

        scale = max(1,(n_syllable * S_DURATION) / float(duration))
        # print('scale',scale,(n_syllable * S_DURATION) / float(duration))
        # if scale != 1:
        #     print('!!!!!!!!!!!!!!!!!!!!!!')
        
        times = np.array(times)
        try:
            times = (times * scale).tolist()
        except:
            times = (np.array([np.array(t) for t in times])*scale).tolist()
            times = [t.tolist() for t in times]
        
        self.s.ALMotion.angleInterpolationBezier(names, times, keys)
        actualduration = time.time() - start
        print('actual',actualduration)
        diff = max(INTERVAL,n_syllable * S_DURATION - actualduration + INTERVAL)
        if n_syllable <= 4:
            diff += 0.3
        time.sleep(diff)
        
        
    def run(self, storyfile):
        story = load_story(storyfile) #read the annotated story
        self.parse_story(story) #parse and perform gestures
                

def load_story(filename):
    with open(filename,'r') as f:
        data = f.read()
    return data

def syllable(word):
    word = word.lower()
    count = 0
    vowels = "aeiouy"
    if word[0] in vowels:
        count += 1
    for index in range(1, len(word)):
        if word[index] in vowels and word[index - 1] not in vowels:
            count += 1
    if word.endswith("e"):
        count -= 1
    return float(count)

def main(ip,port,storyfile):
    nr = NaoRobot(ip,port) #create nao instance
    storyfile = join(cur_d,storyfile) #get absoluth path of the story file
    nr.run(storyfile) #run
    


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--ip", type=str, default="127.0.0.1",
                        help="Robot ip address")
    parser.add_argument("--port", type=str, default="54370",
                        help="Robot port number")
    parser.add_argument("--story", type=str, default="annotated_story.txt", help="File name of the annotated story")

    args = parser.parse_args()
    main(args.ip, args.port, args.story)
