# coding: utf-8
import vanilla
from mojo.extensions import (
    getExtensionDefault,
    setExtensionDefault
)
from mojo.events import postEvent
from mojo.subscriber import (
    Subscriber,
    registerGlyphEditorSubscriber,
    unregisterGlyphEditorSubscriber,
    registerSubscriberEvent,
)
from mojo.UI import (
    getGlyphViewDisplaySettings,
    setGlyphViewDisplaySettings
)
from fontTools.pens.basePen import BasePen
from fontTools.pens.recordingPen import RecordingPen
from fontPens.flattenPen import (
    SamplingPen,
    FlattenPen
)
from fontPens.penTools import (
    estimateCubicCurveLength,
    distance,
    interpolatePoint,
    getCubicPoint,
    getQuadraticPoint
)
from defcon.objects.glyph import Glyph
import ezui
from fontTools.misc.bezierTools import calcCubicArcLength
from itertools import product
import os
import math
import random

'''
CHANGE LOG:
    0.3.0
    Rename to Stroke Scribbler
    0.2.0
    Adding more checks when getting “contour groups" from table selection
    Parse older lib items that we can delete
    Subclassed samplingPen to allow for segmented lines, not just curves
    Combine Sampling and FlattenPens to allow for steps and distances
    Store selected items and rebuild with those selections
    Color picker added
    Custom pen for Sampling AND Flattening


DESCRIPTION

Stroke Scribbler™
Written by Connor Davenport for Kai Bernau

A tool for visualizing and adjusting how a glyph can be drawn using a Noordzijian drawing method.

DOCUMENTATION:

To use this tool, you will need to run this script.
With a glyph window open, either on the default or background layer, break the contours open into contours you wish to "group".
By selecting two *interpolatable* contours selected, click _Add Contour Group_ . After defining a contour group you will be able to adjust 
parameters to your liking. Selecting the group in the UI list, you can batch edit the settings and the glyph will automatically store the new values.
_Generate Contours_ will generate a new background layer with an open contour glyph.


Thickness:                                      Stroke diameter of preview in glyphView
Density:                                        Amount of segments that contours are divided into
Offset:                                         Starting point offset count (1 will offset the next point over and up + 1)
Random:                                         Randomize a jittering effect to simulate a "pen"

( Left | Right )                                Which side the "squiggle" starts from
( Add Contour Group | Delete Contour Group )    Adding and removing selected groups
       
( Generate Contours )                           Generate the preview "squiggle" to a background layer
[X] Preview                                     Toggle visualization

'''

KEY = "com.connordavenport.Stroke"
SETTINGS_KEY = KEY + ".settings"
UI_EVENT_KEY = KEY + ".eventChanged"
DB_EVENT_KEY = KEY + ".drawEventChanged"
LAYER = "Stroke.contourGeneration"
CONTAINER_KEY = KEY + ".container"
COLOR_KEY = KEY + ".color"



class StrokeFlattener(BasePen):
    """
    A custom implimentation of both the FlattenPen and SamplingPen.
    If you give it a dictionary of indexes and point counts as `approximateSegmentLength`, it 
    will sample the glyph but if you give it an integer it will flatten
    """

    def __init__(self, otherPen, approximateSegmentLength=5, segmentLines=False, filterDoubles=True):
        
        self.reference = True if isinstance(approximateSegmentLength, dict) else False
        self.approximateSegmentLength = approximateSegmentLength
        BasePen.__init__(self, {})
        self.otherPen = otherPen
        self.currentPt = None
        self.firstPt = None
        self.segmentLines = segmentLines
        self.filterDoubles = filterDoubles
        self.index = 0
        self.segmentRefrenceMap = {}

    def _moveTo(self, pt):
        self.otherPen.moveTo(pt)
        self.currentPt = pt
        self.firstPt = pt

    def _lineTo(self, pt):
        if self.filterDoubles:
            if pt == self.currentPt:
                return
            
        self.index += 1     
               
        if self.reference:
            steps = self.approximateSegmentLength[self.index] 
            step = 1.0 / steps
            for factor in range(1, steps + 1):
                self.otherPen.lineTo(interpolatePoint(self.currentPt, pt, factor * step))
            self.currentPt = pt
            
        else:
            d = distance(self.currentPt, pt)
            maxSteps = int(round(d / self.approximateSegmentLength))
            if maxSteps < 1:
                self.otherPen.lineTo(pt)
                self.currentPt = pt
                return
            step = 1.0 / maxSteps
            p = 0
            for factor in range(1, maxSteps + 1):
                self.otherPen.lineTo(interpolatePoint(self.currentPt, pt, factor * step))
                p += 1

            self.currentPt = pt
            self.segmentRefrenceMap[self.index] = p
            

    def _curveToOne(self, pt1, pt2, pt3):

        falseCurve = (pt1 == self.currentPt) and (pt2 == pt3)
        if falseCurve:
            self._lineTo(pt3)
            return
            
        self.index += 1
            
        if self.reference:
            falseCurve = (pt1 == self.currentPt) and (pt2 == pt3)
            if falseCurve:
                self._lineTo(pt3)
                return
                
            steps = self.approximateSegmentLength[self.index] 
            step = 1.0 / steps
            for factor in range(1, steps + 1):
                pt = getCubicPoint(factor * step, self.currentPt, pt1, pt2, pt3)
                self.otherPen.lineTo(pt)
            self.currentPt = pt3
           
        else:
            est = estimateCubicCurveLength(self.currentPt, pt1, pt2, pt3) / self.approximateSegmentLength
            maxSteps = int(round(est))
            if maxSteps < 1:
                self.otherPen.lineTo(pt3)
                self.currentPt = pt3
                return
            step = 1.0 / maxSteps
            p = 0
            for factor in range(1, maxSteps + 1):
                pt = getCubicPoint(factor * step, self.currentPt, pt1, pt2, pt3)
                self.otherPen.lineTo(pt)
                p += 1
            self.currentPt = pt3
            self.segmentRefrenceMap[self.index] = p


    def _closePath(self):
        self.lineTo(self.firstPt)
        self.otherPen.closePath()
        self.currentPt = None


    def _endPath(self):
        self.otherPen.endPath()
        self.currentPt = None


    def addComponent(self, glyphName, transformation):
        self.otherPen.addComponent(glyphName, transformation)

'''
Perlin Noise Implimentation by Roberto Arista
'''

def smoothstep(t):
    return t * t * (3. - 2. * t)

def lerp(t, a, b):
    return a + t * (b - a)

def calcAngle(pt1, pt2):
    return math.atan2((pt2[1] - pt1[1]), (pt2[0] - pt1[0]))

def calcMidPoint(pt1, pt2):
    xMid = lerp(.5, pt1[0], pt2[0])
    yMid = lerp(.5, pt1[1], pt2[1])
    return xMid, yMid


class PerlinPen(BasePen):

    def __init__(self, otherPen, intensity,
                 factory, fixedParameters=None):
        BasePen.__init__(self, {})
        self.otherPen = otherPen
        self.pnf = factory
        self.fixedParameters = fixedParameters
        self.intensity = intensity
        self.lastPt = None

    def _moveTo(self, pt):
        self.otherPen.moveTo(pt)
        self.firstPt = self.lastPt = pt

    def _lineTo(self, pt):
        midPt = calcMidPoint(pt, self.lastPt)
        angle = calcAngle(pt, self.lastPt)
        if self.fixedParameters:
            noise = self.pnf(midPt[0], midPt[1], *self.fixedParameters)
        else:
            noise = self.pnf(midPt[0], midPt[1])
        xx = midPt[0] + math.cos(angle+90) * self.intensity*noise
        yy = midPt[1] + math.sin(angle+90) * self.intensity*noise

        self.otherPen.lineTo((xx, yy))
        self.lastPt = pt

    def _curveToOne(self, pt1, pt2, pt3):
        raise NotImplementedError

    def _closePath(self):
        self.lineTo(self.firstPt)
        self.otherPen.closePath()
        self.lastPt = None

    def _endPath(self):
        self.otherPen.endPath()
        self.lastPt = None


def perlinGlyph(aGlyph, intensity, factory, fixedParameters=None):
    if len(aGlyph) == 0:
        return aGlyph
    recorder = RecordingPen()
    filterpen = PerlinPen(recorder, intensity, factory, fixedParameters)
    aGlyph.draw(filterpen)
    aGlyph.clear()
    recorder.replay(aGlyph.getPen())
    return aGlyph


class PerlinNoiseFactory(object):
    def __init__(self, dimension, octaves=1, tile=(), unbias=False):
        self.dimension = dimension
        self.octaves = octaves
        self.tile = tile + (0,) * dimension
        self.unbias = unbias
        self.scale_factor = 2 * dimension ** -0.5
        self.gradient = {}

    def _generate_gradient(self):
        if self.dimension == 1:
            return (random.uniform(-1, 1),)
        random_point = [random.gauss(0, 1) for _ in range(self.dimension)]
        scale = sum(n * n for n in random_point) ** -0.5
        return tuple(coord * scale for coord in random_point)

    def get_plain_noise(self, *point):
        if len(point) != self.dimension:
            raise ValueError("Expected {} values, got {}".format(
                self.dimension, len(point)))
        grid_coords = []
        for coord in point:
            min_coord = math.floor(coord)
            max_coord = min_coord + 1
            grid_coords.append((min_coord, max_coord))
        dots = []
        for grid_point in product(*grid_coords):
            if grid_point not in self.gradient:
                self.gradient[grid_point] = self._generate_gradient()
            gradient = self.gradient[grid_point]
            dot = 0
            for i in range(self.dimension):
                dot += gradient[i] * (point[i] - grid_point[i])
            dots.append(dot)
        dim = self.dimension
        while len(dots) > 1:
            dim -= 1
            s = smoothstep(point[dim] - grid_coords[dim][0])
            next_dots = []
            while dots:
                next_dots.append(lerp(s, dots.pop(0), dots.pop(0)))
            dots = next_dots
        return dots[0] * self.scale_factor

    def __call__(self, *point):
        ret = 0
        for o in range(self.octaves):
            o2 = 1 << o
            new_point = []
            for i, coord in enumerate(point):
                coord *= o2
                if self.tile[i]:
                    coord %= self.tile[i] * o2
                new_point.append(coord)
            ret += self.get_plain_noise(*new_point) / o2
        ret /= 2 - 2 ** (1 - self.octaves)
        if self.unbias:
            r = (ret + 1) / 2
            for _ in range(int(self.octaves / 2 + 0.5)):
                r = smoothstep(r)
            ret = r * 2 - 1
        return ret


def groupList(pairs):
    return [pairs[i * 2:(i + 1) * 2] for i in range((len(pairs) + 2 - 1) // 2 )]  


def addPoints(pt0,pt1):
    return (pt0[0] + pt1[0], pt0[1] + pt1[1])

    
def subtractPoints(pt0,pt1):
    return (pt0[0] - pt1[0], pt0[1] - pt1[1])


def IDtoRContours(glyph,ID):
    allIDS = [(c,c.getIdentifier()) for c in glyph.contours]
    rcs = []
    for i in ID.split(" "):
        for c in glyph.contours:
            if c.identifier == i:
                rcs.append(c)
    return rcs


def getContourPairs(glyph):
    contours = []
    parsed = {}
    if KEY in glyph.lib:
        if glyph.lib[KEY] != {}:
            for contourPair,item in glyph.lib[KEY].items():
                if len(item) == 5:
                    mid,segment,side,offset,random = item
                    parsed[contourPair] = item
                    conts = IDtoRContours(glyph,contourPair)
                    # Currently we will just ignore any contour groups
                    # that are don't have two contours
                    # i.e if you delete one contour
                    # should we also just delete that from the lib? Maybe...
                    if len(conts) == 2:
                        contours.append((conts,(mid,segment,side,offset,random)))
    return contours


def getSelectedPair(glyph):
    selected = glyph.selectedContours
    selIDs = []
    if len(selected) == 2:
        selIDs = sorted([cs.getIdentifier() for cs in selected])
    return selIDs
    

fallback_settings = {
    'thicknessSlider' : 4,
    'flattenSlider'   : 35.0,
    'offsetSlider'    : 0.0,
    'randomSlider'    : 0.0,
    'side'            : 0,
    'editGroups'      : None,
    'groupTable'      : [],
    'colorWell'       : (1.0, 1.0, 1.0, 1.0),
    'preview'         : 1
}

colors = {

    'purple' :  (0.5819, 0.2157, 1.0, 1.0),
    'green' :  (0.04, 0.57, 0.04, 1.0),
    'orange' :  (0.99, 0.62, 0.11, 1.0),
    'brown' :  (0.4791, 0.2884, 0.0, 1.0),
}

basePath = os.path.dirname(__file__)
resourcesPath = os.path.join(basePath, "resources")

_thickness_symbol = ezui.makeImage(
            symbolName="pencil.tip",
            imagePath=os.path.join(resourcesPath, "pencil.tip.png"),
            template=True
            # symbolConfiguration=dict(
            #     colors=[colors.get("purple")]
            # )
)
_density_symbol = ezui.makeImage(
            symbolName="circle.hexagonpath.fill",
            imagePath=os.path.join(resourcesPath, "circle.hexagonpath.fill.png"),
            template=True
            # symbolConfiguration=dict(
            #     colors=[colors.get("green")]
            # )
)
_side_symbol = ezui.makeImage(
            symbolName="arrowshape.left.arrowshape.right.fill",
            imagePath=os.path.join(resourcesPath, "arrowshape.left.arrowshape.right.fill.png"),
            template=True
            # symbolConfiguration=dict(
            #     colors=[colors.get("blue")]
            # )
)
_offset_symbol = ezui.makeImage(
            symbolName="arrow.down.left.and.arrow.up.right",
            imagePath=os.path.join(resourcesPath, "arrow.down.left.and.arrow.up.right.png"),
            template=True
            # symbolConfiguration=dict(
            #     colors=[colors.get("brown")]
            # )
)
_random_symbol = ezui.makeImage(
            symbolName="pencil.and.scribble",
            imagePath=os.path.join(resourcesPath, "pencil.and.scribble.png"),
            template=True
            # symbolConfiguration=dict(
            #     colors=[colors.get("orange")]
            # )
)

class StrokeScribblerWindowController(Subscriber, ezui.WindowController):

    def build(self):
        self.settings  = []
        self.selected = None

        content = """
        
        * HorizontalStack

        > * VerticalStack 
        >> Thickness:                                             @thicknessText
        >> ---X--- [__](±)                                        @thicknessSlider
        >> Density:                                               @flattenText
        >> ---X--- [__](±)                                        @flattenSlider         
        >> Offset:                                                @offsetText
        >> ---X--- [__](±)                                        @offsetSlider
        >> Random:                                                @randomText
        >> ---X--- [__](±)                                        @randomSlider

        >> --------
                      
        >> ( Left | X Right X )                                   @side

        >> ((( Add Contour Group | Delete Contour Group )))       @editGroups

        >> * VerticalStack

        >>> |------------------------|                            @groupTable
        >>> | na | th | fl | si | of |   
        >>> |----|----|----|----|----|
        >>> |    |    |    |    |    |    
        >>> |    |    |    |    |    |
        >>> |------------------------|

        >> ( Generate Contours )                                  @generate

        >> * ColorWell                                            @colorWell
        >> [X] Preview                                            @preview
        """

        mini_col = 40

        descriptionData = dict(

            side=dict(
                width="fill",
            ),

            editGroups=dict(
                width="fill",
            ),

            colorWell=dict(
                colorWellStyle="minimal",
                color=(1,1,1,1),
            ),

            thicknessSlider=dict(
                valueType="integer",
                minValue=1,
                maxValue=20,
                value=4,
                tickMarks=21,
                stopOnTickMarks=True,
            ),

            offsetSlider=dict(
                valueType="integer",
                minValue=0,
                maxValue=4,
                value=1,
                tickMarks=5,
                stopOnTickMarks=True,
            ),

            flattenSlider=dict(
                valueType="integer",
                minValue=10,
                maxValue=100,
                value=20,
                tickMarks=19,
                stopOnTickMarks=True,
            ),
            randomSlider=dict(
                valueType="integer",
                minValue=0,
                maxValue=10,
                value=0,
                tickMarks=11,
                stopOnTickMarks=True,
            ),

            groupTable=dict(
                width=400,
                height=400,
                items=self.settings,
                columnDescriptions=[
                    dict(
                        identifier="group_index",
                        title="Group Index",
                        editable=False,
                    ),
                    dict(
                        identifier="thickness_settings",
                        # title=_thickness_symbol,
                        title="Thi",
                        width=mini_col,
                        editable=False,
                        ),
                    dict(
                        identifier="flatten_settings",
                        # title=_density_symbol,
                        title="Den",
                        width=mini_col,
                        editable=False,
                        ),
                    dict(
                        identifier="side_settings",
                        # title=_side_symbol,
                        title="Side",
                        width=mini_col,
                        editable=False,
                        ),
                    dict(
                        identifier="offset_settings",
                        # title=_offset_symbol,
                        title="Off",
                        width=mini_col,
                        editable=False,
                        ),
                    dict(
                        identifier="random_settings",
                        # title=_random_symbol,
                        title="Rnd",
                        width=mini_col,
                        editable=False,
                        )
                    ]
                )
            )
        self.w = ezui.EZWindow(
            title="StrokeScribbler",
            size=("auto", "auto"),
            content=content,
            descriptionData=descriptionData,
            controller=self
        )

        data = getExtensionDefault(SETTINGS_KEY, fallback_settings)
        self.w.setItemValues(data)

        tooltip_dict = {
            "thickness" : "Thickness of each stroke",
            "flatten"   : "Density of flatted contour",
            "offset"    : "Amount of steps are skipped on the opposite side",
            "random"    : "Randomness of to the stroke",
        }

        for title, description in tooltip_dict.items():
            for sub in ["Text", "Slider"]:
                _id = f"{title}{sub}"
                self.w.getItem(_id).setToolTip(description),
                # TIL that autoRepeat does not fix wrapping issue, we need
                # to use setValueWraps_ on the nsObject instead 
                if sub == "Slider":
                    stepper = self.w.getItem(_id)._get_stepper()
                    stepper._nsObject.setValueWraps_(False)

        self.w.getItem("preview").setToolTip("Will draw stroke")
        self.w.getItem("side").setToolTip("The side of the contour that the drawing starts on")

        self.contours = []

        self.thickness =   int(self.w.getItem("thicknessSlider").get())
        self.flatten   =   int(self.w.getItem("flattenSlider").get())
        self.side      =   int(self.w.getItem("side").get())
        self.offset    =   int(self.w.getItem("offsetSlider").get())
        self.preview   =   int(self.w.getItem("preview").get())
        self.random    =   int(self.w.getItem("randomSlider").get())

        self.color     = tuple(self.w.getItem("colorWell").get())

        self.selectionIndexes = []
        self.fixing = False

        self.currentGlyph = CurrentGlyph()
        self.rebuildTableItems(self.currentGlyph)


    def started(self):
        self.fill = getGlyphViewDisplaySettings()['Fill']
        setGlyphViewDisplaySettings({'Fill': False})
        self.w.open()
        registerGlyphEditorSubscriber(StrokeScribblerDrawingBot)


    def destroy(self):
        if self.fill: setGlyphViewDisplaySettings({'Fill': True})
        unregisterGlyphEditorSubscriber(StrokeScribblerDrawingBot)
        setExtensionDefault(SETTINGS_KEY, self.w.getItemValues())
    
 
    def colorWellCallback(self,sender):
        self.color = tuple(sender.get())
        postEvent(UI_EVENT_KEY, color_value=tuple(sender.get()))
        self.currentGlyph.lib[COLOR_KEY] = self.color
        self.currentGlyph.lib.changed()


    def groupTableSelectionCallback(self,sender):
        self.selected = sender.getSelectedItems() if sender.getSelectedItems() else []
        self.selectionIndexes = sender.getSelectedIndexes() if sender.getSelectedIndexes() else []
        if not self.fixing:
            for c in self.currentGlyph:
                c.selected = False
            if self.selected:
                for curSel in self.selected:
                    stp = getContourPairs(self.currentGlyph)
                    si  = int(curSel["group_index"])
                    cps = stp[si][0]

                    for c in self.currentGlyph:
                        if c.getIdentifier() in [r.getIdentifier() for r in cps]:
                            c.selected = True

                    self.w.getItem("thicknessSlider").set(curSel["thickness_settings"])
                    self.w.getItem("flattenSlider").set(curSel["flatten_settings"])
                    self.w.getItem("side").set(curSel["side_settings"])
                    self.w.getItem("offsetSlider").set(curSel["offset_settings"])
                    self.w.getItem("randomSlider").set(curSel["random_settings"])
            else:
                for c in self.currentGlyph:
                    c.selected = False


    def thicknessSliderCallback(self,sender):
        self.currentGlyph = CurrentGlyph()
        self.thickness = int(sender.get())
        self.setSelected((self.thickness, 0))
        postEvent(UI_EVENT_KEY, thickness_value=sender.get())


    def flattenSliderCallback(self,sender):
        self.currentGlyph = CurrentGlyph()
        self.flatten = int(sender.get())
        self.setSelected((self.flatten, 1))
        postEvent(UI_EVENT_KEY, flatten_value=sender.get())


    def sideCallback(self,sender):
        self.side = int(sender.get())
        self.setSelected((self.side, 2))
        postEvent(UI_EVENT_KEY, side_value=sender.get())


    def offsetSliderCallback(self,sender):
        self.currentGlyph = CurrentGlyph()
        self.offset = int(sender.get())
        self.setSelected((self.offset, 3))
        postEvent(UI_EVENT_KEY, offset_value=sender.get())


    def randomSliderCallback(self,sender):
        self.currentGlyph = CurrentGlyph()
        self.random = int(sender.get())
        self.setSelected((self.random, 4))
        postEvent(UI_EVENT_KEY, random_value=sender.get())


    def setSelected(self, valIndex):
        value,index = valIndex
        conts = getContourPairs(self.currentGlyph)
        if self.selected:
            for group in self.selected:

                gg = conts[int(group["group_index"])]
                ci = " ".join(sorted([b.getIdentifier() for b in gg[0]]))

                lib = self.currentGlyph.lib[KEY]
                v = list(gg[1])
                v[index] = value
                lib[ci] = tuple(v)

                self.currentGlyph.lib[KEY] = lib

        self.currentGlyph.lib.changed()
        self.rebuildTableItems(self.currentGlyph)


    def rebuildTableItems(self, glyph):
        if glyph is not None:
            items = []
            for i,s in enumerate(getContourPairs(glyph)):

                ir = dict(group_index         = str(i),
                          thickness_settings = s[1][0],
                          flatten_settings   = s[1][1],
                          side_settings      = s[1][2],
                          offset_settings    = s[1][3],
                          random_settings    = s[1][4])
                items.append(ir)
            self.settings = items
            self.w.getItem("groupTable").set(self.settings)

        if self.selectionIndexes: 
            self.fixing = True
            self.w.getItem("groupTable").setSelectedIndexes(self.selectionIndexes)
            self.fixing = False


    def editGroupsCallback(self,sender):
        if sender.get() == 0:
            c = self.currentGlyph.selectedContours

            if len(c) == 2:
                if self.currentGlyph.lib.get(KEY):
                    lib = self.currentGlyph.lib[KEY]
                else:
                    lib = {}
                    
                ci = " ".join(sorted([b.getIdentifier() for b in c]))
                lib[ci] = (self.thickness,self.flatten,self.side,self.offset,self.random)

                self.currentGlyph.lib[KEY] = lib
                self.selectionIndexes = [len(lib)-1,]
        else:
            selectedPair = getSelectedPair(self.currentGlyph)
            if KEY in self.currentGlyph.lib:
                tempDict = self.currentGlyph.lib[KEY]
                for contourPair in list(tempDict.keys()):
                    if " ".join(selectedPair) == contourPair:
                        del tempDict[contourPair]
                self.currentGlyph.lib[KEY] = tempDict

            self.selectionIndexes = []

        self.currentGlyph.lib.changed()
        self.rebuildTableItems(self.currentGlyph)
        postEvent(UI_EVENT_KEY, draw=True)


    def generateCallback(self,sender):
        g = self.currentGlyph
        if LAYER in g.font.layerOrder:
            pass
        else:
            g.font.newLayer(LAYER)
            
        drawLayer = g.getLayer(LAYER)
        drawLayer.clear()
        pen = drawLayer.getPen()
        for i, gs in enumerate(self.contours):
            pen.moveTo(gs[0])
            for s in gs[1:]:
                pen.lineTo(s)
            pen.endPath()


    def previewCallback(self,sender):
        postEvent(UI_EVENT_KEY, show_preview=sender.get())


    def reselectTable(self):
        self.fixing = True
        stp = getContourPairs(self.currentGlyph)
        sel = []
        for io, cps in enumerate(stp):
            (c1,c2),_ = cps
            if c1.selected and c2.selected:
                sel.append(io)
        self.selectionIndexes = sel
        self.fixing = False


    def drawSettingsChanged(self, info):
        if info["contours"] is not None:
            self.contours = info["contours"]  
            self.reselectTable()
        if info["reset_glyph"] is not None:
            self.currentGlyph = info["reset_glyph"]
            self.selectionIndexes = []

        self.rebuildTableItems(self.currentGlyph)
        
        
class StrokeScribblerDrawingBot(Subscriber):

    def build(self):
        glyphEditor = self.getGlyphEditor()
        self.container = glyphEditor.extensionContainer(CONTAINER_KEY, location="background")

        self.contoursLayer = self.container.appendPathSublayer(
            strokeColor=None,
            strokeWidth=None,
            fillColor=None,
        )

        self.thickness = 1
        self.flatten = 40
        self.side = 1
        self.offset = 1
        self.random = 0
        self.preview = 1
        self.contours = []
        self.color = (1,1,1,1)
        self.currentGlyph = RGlyph(glyphEditor.getGlyph())


    def destroy(self):
        self.container.clearSublayers()


    def drawContour(self, contour, color, stroke_size, seg_length, random, amount=None, side="one"):
        glyph = Glyph()
        outputPen = glyph.getPen()
        flattenPen = StrokeFlattener(outputPen, approximateSegmentLength=seg_length)
        contour.draw(flattenPen)

        pnf = PerlinNoiseFactory(2, octaves=4, tile=(1000/600, 1000/600))
        perlinGlyph(glyph, random * 10, pnf)
        flat = glyph[0] 

        layer = self.contoursLayer.appendPathSublayer(
            fillColor=None,
            strokeColor=None,
            strokeWidth=1,
            )
        p = flat.getRepresentation("merz.CGPath")
        layer.setPath(p)
        return ([(point.x, point.y) for point in flat], flattenPen.segmentRefrenceMap)


    def glyphEditorDidSetGlyph(self, info):
        self.currentGlyph = info['glyph']
        if self.currentGlyph is not None:
            lib = self.currentGlyph.lib.get(KEY)
            if lib:
                parsed = {name:item for name,item in lib.items() if len(item) == 5}
                # self.currentGlyph.lib[KEY] = parsed

            self.selectionIndexes = []
            postEvent(DB_EVENT_KEY, reset_glyph=self.currentGlyph)
            self.draw()


    def glyphEditorGlyphDidChangeSelection(self, info):
        self.currentGlyph = info['glyph']
        if self.currentGlyph is not None:
            if self.currentGlyph.selectedContours:
                postEvent(DB_EVENT_KEY, contours=self.currentGlyph)
                # self.draw()


    def glyphEditorGlyphDidChange(self, info):
        self.currentGlyph = info['glyph']
        if self.currentGlyph is not None:
            postEvent(DB_EVENT_KEY, reset_glyph=self.currentGlyph)
            self.draw()

        
    def glyphEditorDidMouseDrag(self, info):
        self.currentGlyph = info['glyph']
        if self.currentGlyph is not None:
            postEvent(DB_EVENT_KEY, reset_glyph=self.currentGlyph)
            self.draw()


    def draw(self, isSelected=False):
        # Draw the interpolated glyph outlines
        if self.preview:
            self.contours = []
            self.contoursLayer.clearSublayers()
            if self.currentGlyph:

                # if getContourPairs(self.currentGlyph) != [[],[]]:
                selIDs = getSelectedPair(self.currentGlyph)
                cps = getContourPairs(self.currentGlyph)
                for c in cps:

                    parsedContours = c[0]
                    cinfo          = c[1]
                    cont1,cont2    = parsedContours

                    if isSelected:
                        fill = (0,1,1,1)

                    fill   = self.color
                    mid    = cinfo[0]
                    segs   = cinfo[1]
                    side   = cinfo[2]
                    offset = cinfo[3]
                    random = cinfo[4]
                    ps1,ref = self.drawContour(
                        contour     = cont1,
                        color       = (1,0,0,1),
                        stroke_size = 3,
                        seg_length  = segs,
                        random      = random,
                        side        = "one"
                    )
                    ps2,_ = self.drawContour(
                        contour     = cont2,
                        color       = (0.0, 0.9811, 0.5737, 1.0),
                        stroke_size = 3,
                        seg_length  = ref,
                        random      = random,
                        side        = "two"
                    )
                    if side:
                        ps1,ps2 = ps2,ps1

                    squiggle = self.contoursLayer.appendPathSublayer(
                        strokeColor = fill,
                        strokeWidth = mid,
                        fillColor   = None,
                        strokeCap   = "round",
                        strokeJoin  = "round",
                        )
                    pen = squiggle.getPen()

                    it = []
                    pen.moveTo(ps1[0])
                    it.append(ps1[0])

                    for i, ps in enumerate(ps1):
                        try:
                            ops = ps2[i + offset]
                            pen.lineTo(ops)
                            pen.lineTo(ps)
                            it.append(ops)
                            it.append(ps)
                        except IndexError:
                            pass

                    pen.endPath()
                    self.contours.append(it)

        postEvent(DB_EVENT_KEY, contours=self.contours)


    def settingsChanged(self, info):
        # LongboardEditorView
        if info["thickness_value"] is not None:
            self.thickness = info["thickness_value"]
        if info["flatten_value"] is not None:
            self.flatten = info["flatten_value"]
        if info["side_value"] is not None:
            self.side = info["side_value"]
        if info["offset_value"] is not None:
            self.offset = info["offset_value"]
        if info["random_value"] is not None:
            self.random = info["random_value"]
        if info["show_preview"] is not None:
            self.preview = info["show_preview"]        
        if info["color_value"] is not None:
            self.color = info["color_value"]        
        self.draw()


def previewSettingsExtractor(subscriber, info):
    # crikey there as to be a more efficient way to do this.
    info["thickness_value"] = None
    info["flatten_value"] = None
    info["side_value"] = None
    info["offset_value"] = None
    info["random_value"] = None
    info["show_preview"] = None
    info["color_value"] = None
    for lowLevelEvent in info["lowLevelEvents"]:
        info["thickness_value"] = lowLevelEvent.get("thickness_value")
        info["flatten_value"] = lowLevelEvent.get("flatten_value")
        info["side_value"] = lowLevelEvent.get("side_value")
        info["offset_value"] = lowLevelEvent.get("offset_value")
        info["random_value"] = lowLevelEvent.get("random_value")
        info["show_preview"] = lowLevelEvent.get("show_preview")
        info["color_value"] = lowLevelEvent.get("color_value")

def drawingPreviewSettingsExtractor(subscriber, info):
    # crikey there as to be a more efficient way to do this.
    info["contours"] = None
    info["reset_glyph"] = None
    for lowLevelEvent in info["lowLevelEvents"]:
        info["contours"] = lowLevelEvent.get("contours")
        info["reset_glyph"] = lowLevelEvent.get("reset_glyph")


registerSubscriberEvent(
    subscriberEventName=UI_EVENT_KEY,
    methodName="settingsChanged",
    lowLevelEventNames=[UI_EVENT_KEY],
    eventInfoExtractionFunction=previewSettingsExtractor,
    dispatcher="roboFont",
    delay=0,
    debug=True
)

registerSubscriberEvent(
    subscriberEventName=DB_EVENT_KEY,
    methodName="drawSettingsChanged",
    lowLevelEventNames=[DB_EVENT_KEY],
    eventInfoExtractionFunction=drawingPreviewSettingsExtractor,
    dispatcher="roboFont",
    delay=0,
    debug=True
)


if __name__ == "__main__":
    OpenWindow(StrokeScribblerWindowController)

                