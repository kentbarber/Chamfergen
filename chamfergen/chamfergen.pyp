"""
MIT License

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
"""

import c4d
from c4d import utils   
import math
ID_CHAMFERGEN = 1056988

ID_CHAMFERGEN_SELECTIONANGLE = 1000
ID_CHAMFERGEN_INPUTLINK = 1001
ID_CHAMFERGEN_SPLINETYPE = 1002
ID_CHAMFERGEN_LINEAR = 0
ID_CHAMFERGEN_AKIMA = 1
ID_CHAMFERGEN_BSPLINE = 2
ID_CHAMFERGEN_SUBDIVISIONS = 1003
ID_CHAMFERGEN_OVERRIDETYPE = 1004
ID_CHAMFERGEN_FLAT = 1005
ID_CHAMFERGEN_RADIUS = 1006
ID_CHAMFERGEN_OPTIMIZEANGLE = 1007
ID_CHAMFERGEN_POINTSELECTION = 1008
ID_CHAMFERGEN_MODE = 1009
ID_CHAMFERGEN_CHAMFER = 0
ID_CHAMFERGEN_OFFSET = 1
ID_CHAMFERGEN_DISTANCE = 1010

def CheckSelfReferencing(startObject, op):
    objectStack = []
    objectStack.append(startObject)

    firstObject = True

    while objectStack:
        currentObject = objectStack.pop()
        if currentObject == op:
            return True

        downObject = currentObject.GetDown()
        if downObject is not None:
            objectStack.append(downObject)

        if not firstObject:
            nextObject = currentObject.GetNext()
            if nextObject is not None:
                objectStack.append(nextObject)
        
        firstObject = False
        
    return False

def CollectChildDirty(startObject, op, ignoreFirst):
    objectStack = []
    objectStack.append(startObject)

    firstObject = True
    dirtyCount = 0
    while objectStack:
        currentObject = objectStack.pop()

        downObject = currentObject.GetDown()
        if downObject is not None and downObject != op:
            objectStack.append(downObject)

        if not firstObject:
            nextObject = currentObject.GetNext()
            if nextObject is not None and nextObject != op:
                objectStack.append(nextObject)

        if ignoreFirst and firstObject:
            firstObject = False
            continue

        dirtyCount += currentObject.GetDirty(c4d.DIRTYFLAGS_DATA | c4d.DIRTYFLAGS_MATRIX | c4d.DIRTYFLAGS_CACHE)

        firstObject = False

    return dirtyCount

def CollectSplineObjects(startObject, op, ignoreFirst, hierarchyCloneMode, hh):
    splineList = []
    hierObjectStack = []
    objectStackStart = []
    objectStack = []
    foundObjects = 0

    if hierarchyCloneMode: 
        op.NewDependenceList()
        for child in op.GetChildren():
            foundObjects = 0
            clones = op.GetHierarchyClone(hh, child, c4d.HIERARCHYCLONEFLAGS_ASSPLINE, None, None, c4d.DIRTYFLAGS_DATA | c4d.DIRTYFLAGS_MATRIX)
            #for clone in clones:
            if clones["clone"] is not None:
                hierObjectStack.append(clones["clone"])

            while hierObjectStack:
                currentObject = hierObjectStack.pop()
                if currentObject.IsInstanceOf(c4d.Oline) or currentObject.IsInstanceOf(c4d.Ospline):
                    foundObjects += 1

                nextObject = currentObject.GetNext()
                if nextObject is not None and nextObject != op:
                    hierObjectStack.append(nextObject)

                downObject = currentObject.GetDown()
                if downObject is not None and downObject != op:
                    hierObjectStack.append(downObject)
            objectStackStart.append((child, foundObjects))
            ignoreFirst = False
    else:
          objectStackStart.append((startObject, 0))

    for objectStart in objectStackStart:
        foundObjects = objectStart[1]
        objectStack.append(objectStart[0])
        firstObject = True
        while objectStack:
            currentObject = objectStack.pop()
            downObject = currentObject.GetDown()
            goDownAnyways = not hierarchyCloneMode and firstObject
            inputGenerator = currentObject.GetInfo() & c4d.OBJECT_INPUT != 0 and currentObject.GetDeformMode()
            
            if downObject is not None and downObject != op and (goDownAnyways or not inputGenerator):
                objectStack.append(downObject)

            if not firstObject:
                nextObject = currentObject.GetNext()
                if nextObject is not None and nextObject != op:
                    objectStack.append(nextObject)

            if ignoreFirst and firstObject:
                firstObject = False
                continue

            currentContour = None

            """
            if currentObject.GetDeformMode() == True:
                currentContour = currentObject.GetRealSpline()
                if currentContour is None and currentObject.GetCache():
                    objectStack.append(currentObject.GetCache())"""
            if currentObject.GetDeformMode() == True:
                if currentObject.GetCache() and not currentObject.IsInstanceOf(c4d.Ospline):
                    objectStack.append(currentObject.GetCache())

            if currentContour is not None:
                objectMat = currentObject.GetMg()
                currentObject = currentContour;
                currentObject.SetMg(objectMat)

            if currentObject.IsInstanceOf(c4d.Oline):  
                parent = currentObject.GetCacheParent()
                if parent:
                    spline = parent.GetRealSpline()
                    if spline:
                        objectMat = currentObject.GetMg()
                        currentObject = spline
                        currentObject.SetMg(objectMat)

            if currentObject.IsInstanceOf(c4d.Ospline):
                foundObjects -= 1
                if currentObject.GetPointCount() > 0:
                    objectCopy = currentObject.GetClone(c4d.COPYFLAGS_NO_HIERARCHY | c4d.COPYFLAGS_NO_ANIMATION | c4d.COPYFLAGS_NO_BITS)
                    
                    if hierarchyCloneMode:
                        objectCopy.SetMg(~op.GetMg() * currentObject.GetMg())
                    else:
                        objectCopy.SetMg(currentObject.GetMg())
                    splineList.append(objectCopy)
                if foundObjects == 0:
                    break

            firstObject = False
    return splineList

def TransferSplineMode(targetSpline, op):
    type = op[ID_CHAMFERGEN_SPLINETYPE]
    subdivisions = op[ID_CHAMFERGEN_SUBDIVISIONS]

    if type == ID_CHAMFERGEN_LINEAR:
        targetSpline[c4d.SPLINEOBJECT_TYPE] = c4d.SPLINEOBJECT_TYPE_LINEAR
    elif type == ID_CHAMFERGEN_AKIMA:
        targetSpline[c4d.SPLINEOBJECT_TYPE] = c4d.SPLINEOBJECT_TYPE_AKIMA
    elif type == ID_CHAMFERGEN_BSPLINE:
        targetSpline[c4d.SPLINEOBJECT_TYPE] = c4d.SPLINEOBJECT_TYPE_BSPLINE

    targetSpline[c4d.SPLINEOBJECT_INTERPOLATION] = c4d.SPLINEOBJECT_INTERPOLATION_UNIFORM
    targetSpline[c4d.SPLINEOBJECT_SUB] = subdivisions

def OptimizeSpline(splineObj):
    """detect if all segments of this spline are closed by having the same start and end point"""
    """if that is the case, remove the end point and set the spline to be closed instead"""
    segmentTag = splineObj.GetTag(c4d.Tsegment)

    if segmentTag is not None:
        segData = segmentTag.GetAllHighlevelData()
        segmentStart = 0
        # first check if we cann optimize the spline
        for segment in segData:
            segmentCount = segment["cnt"]
            if segmentCount > 2:
                if (splineObj.GetPoint(segmentStart) - splineObj.GetPoint(segmentStart + segmentCount - 1)).GetLengthSquared() > 0.00001:
                    # at least one segment cannot be closed without large error, so the spline is not optimized into an closed loop
                    return
            else:
                return

            segmentStart = segmentStart + segmentCount
        # remove all endpoint of each segment and shift the points
        points = splineObj.GetAllPoints()
        splineObj.ResizeObject(splineObj.GetPointCount() - len(segData), splineObj.GetSegmentCount())
        
        segDataWritable = segmentTag.GetLowlevelDataAddressW()
        segDataSize = segmentTag.GetDataSize()

        segmentIndex = 0
        pointIndex = 0
        for segment in segData:
            segmentCount = segment["cnt"]

            # override segmentpoints except the last point
            # targetindex is the pointindex minus the segmentindex, because those are the previously removed points
            for indexOffset in range(segmentCount - 1):
                splineObj.SetPoint(pointIndex - segmentIndex + indexOffset, points[pointIndex + indexOffset])

            # reduce the segment pointcount by one
            if segDataWritable is not None:
                byteShift = 0
                # because these are bytes, byteshifts need to be done manually on decrement (honestly :D)
                while byteShift < 4 and segDataWritable[segmentIndex * segDataSize + byteShift] == 0:
                    segDataWritable[segmentIndex * segDataSize + byteShift] = 255
                    byteShift = byteShift + 1

                segDataWritable[segmentIndex * segDataSize + byteShift] = segDataWritable[segmentIndex * segDataSize + byteShift] - 1


            pointIndex = pointIndex + segmentCount
            segmentIndex = segmentIndex + 1
        
        splineObj[c4d.SPLINEOBJECT_CLOSED] = True

def GetAngleBasedPointIndices(splineObj, selectionAngle, bigger):
    angleIndices = []
    if not splineObj.IsInstanceOf(c4d.Ospline):
        return angleIndices

    segmentTag = splineObj.GetTag(c4d.Tsegment)
    segData = None
    segmentStart = 0
    if segmentTag is not None:
        segData = segmentTag.GetAllHighlevelData()
    else:
        segData = []
        segDataEntry = dict()
        segDataEntry["cnt"] = splineObj.GetPointCount()
        segDataEntry["closed"] = splineObj[c4d.SPLINEOBJECT_CLOSED] 
        segData.append(segDataEntry)

    selectionAngleCos = math.cos(selectionAngle)
    if segData is not None:
        for segment in segData:
            segmentCount = segment["cnt"]
            segmentClosed = splineObj[c4d.SPLINEOBJECT_CLOSED]
            if segmentCount > 2 or (segmentCount == 2 and segmentClosed):
                for segmentIndex in range(segmentCount):
                    nextIndex = segmentIndex + 1
                    prevIndex = segmentIndex - 1
                    if nextIndex >= segmentCount:
                        if segmentClosed:
                            nextIndex = 0
                        else:
                            continue

                    if prevIndex < 0:
                        if segmentClosed:
                            prevIndex = segmentCount - 1
                        else:
                            continue

                    forwardVec = splineObj.GetPoint(segmentStart + nextIndex)- splineObj.GetPoint(segmentStart + segmentIndex)
                    backVec = splineObj.GetPoint(segmentStart + prevIndex) - splineObj.GetPoint(segmentStart + segmentIndex)
                    forwardVec.Normalize()
                    backVec.Normalize()
                    if bigger:
                        if c4d.Vector.Dot(forwardVec, backVec) + 1e-9 >= selectionAngleCos:
                            angleIndices.append(segmentStart + segmentIndex)
                    else:
                        if c4d.Vector.Dot(forwardVec, backVec) - 1e-9 <= selectionAngleCos:
                            angleIndices.append(segmentStart + segmentIndex)


            segmentStart = segmentStart + segmentCount
    return angleIndices
            
def ProcessPointSelectionTag(splineObj, selectionName):
    hadSelection = False

    targetPointSel = splineObj.GetPointS()
    targetPointSel.DeselectAll()
    if selectionName is not None and selectionName != "":
        tagObj = splineObj.GetFirstTag()

        while tagObj:
            if tagObj.GetName() == selectionName:
                if tagObj.IsInstanceOf(c4d.Tpointselection):
                    baseSelectNew = tagObj.GetBaseSelect()
                    if baseSelectNew.GetCount() > 0:
                        hadSelection = True
                    targetPointSel.Merge(baseSelectNew)
                    break
            tagObj = tagObj.GetNext()

    return hadSelection

def ProcessPointSelection(splineObj, selectionAngle):
    pointIndices = GetAngleBasedPointIndices(splineObj, selectionAngle, True)
    selection = splineObj.GetPointS()
    selection.DeselectAll()
    if pointIndices is not None and len(pointIndices) > 0:
        for pointIndex in range(len(pointIndices)):
            selection.Select(pointIndices[pointIndex])

        return True
    else:
        return False

def OptimizeCollinearPoints(splineObj, selectionAngle):
    pointIndices = GetAngleBasedPointIndices(splineObj, selectionAngle, False)

    if pointIndices is not None and len(pointIndices) > 0:

        selection = splineObj.GetPointS()
        storeTag = splineObj.MakeTag(c4d.Tpointselection)
        storeBase = storeTag.GetBaseSelect()
        storeBase.Merge(selection)
        selection.DeselectAll()

        for pointIndex in range(len(pointIndices)):
            selection.Select(pointIndices[pointIndex])

        settings = c4d.BaseContainer()
        res = utils.SendModelingCommand(command=c4d.MCOMMAND_DELETE,
                            list=[splineObj],
                            mode=c4d.MODELINGCOMMANDMODE_POINTSELECTION,
                            bc=settings,
                            doc=None)
        selection.DeselectAll()
        selection.Merge(storeBase)
        storeTag.Remove()

def HideParameter(node, desc, id, state):
    para = desc.GetParameter(id)
    para[c4d.DESC_HIDE] = state
    desc.SetParameter(id, para, c4d.DESCID_ROOT)

class ChamfergenObjectData(c4d.plugins.ObjectData):

    def __init__(self):
        self.inputLinkMatrixDirty = 0
        self.selfDirtyCount = 0
        self.prevChildDirty = 0

    def Init(self, node):
        
        node[ID_CHAMFERGEN_SPLINETYPE] = ID_CHAMFERGEN_LINEAR
        node[ID_CHAMFERGEN_SUBDIVISIONS] = 0
        node[ID_CHAMFERGEN_OVERRIDETYPE] = False
        
        node[ID_CHAMFERGEN_OPTIMIZEANGLE] = 0.0
        node[ID_CHAMFERGEN_MODE] = ID_CHAMFERGEN_CHAMFER

        """Chamfer settings"""
        node[ID_CHAMFERGEN_FLAT] = False
        node[ID_CHAMFERGEN_RADIUS] = 20.0
        node[ID_CHAMFERGEN_SELECTIONANGLE] = 0.698132
        node[ID_CHAMFERGEN_POINTSELECTION] = ""

        """Offset setting"""
        node[ID_CHAMFERGEN_DISTANCE] = 10.0

        """set a generator like color override for the icon"""
        node[c4d.ID_BASELIST_ICON_COLORIZE_MODE] = c4d.ID_BASELIST_ICON_COLORIZE_MODE_CUSTOM
        node[c4d.ID_BASELIST_ICON_COLOR] = c4d.Vector(153.0 / 255.0, 1.0 , 173.0 / 255.0)
        return True

    def OffsetSpline(self, startObject, op, ignoreFirst, hierarchyCloneMode, hh):
        splineOutputs = []
        settings = c4d.BaseContainer()
        settings[c4d.MDATA_SPLINE_OUTLINE] = op[ID_CHAMFERGEN_DISTANCE]
        splineObjList = CollectSplineObjects(startObject, op, ignoreFirst, hierarchyCloneMode, hh)
        if len(splineObjList) == 0:
            return None
        # call edge to spline modeling command
        for splineObj in splineObjList:

            optimizeAngle = op[ID_CHAMFERGEN_OPTIMIZEANGLE]
            if optimizeAngle != 0.0:
                OptimizeCollinearPoints(splineObj, math.pi - optimizeAngle)

            res = utils.SendModelingCommand(command=c4d.MCOMMAND_SPLINE_CREATEOUTLINE,
                                list=[splineObj],
                                mode=c4d.MODELINGCOMMANDMODE_POINTSELECTION,
                                bc=settings,
                                doc=None)
            if splineObj != None:
                splineObj.Remove()
                OptimizeSpline(splineObj)
                selection = splineObj.GetPointS()
                selection.DeselectAll()
                splineOutputs.append(splineObj)


        if len(splineOutputs) == 0:
            return None
        returnObject = None

        # join the splines if multiple input objects were found
        if len(splineOutputs) > 1:
            doc = op.GetDocument()
            tempdoc = c4d.documents.BaseDocument()
            
            for spline in splineOutputs:
                tempdoc.InsertObject(spline)

            settings[c4d.MDATA_JOIN_MERGE_SELTAGS] = True
            res = utils.SendModelingCommand(command=c4d.MCOMMAND_JOIN,
                                list=splineOutputs,
                                mode=1032176,
                                bc=settings,
                                doc=tempdoc)

            if isinstance(res, list):
                res[0].SetMg(c4d.Matrix())
                returnObject = res[0]
        

        if len(splineOutputs) == 1:
            returnObject = splineOutputs[0]

        genMat = op.GetMg()
        # transform the spline points into generator space. Otherwise cloner has issues cloning
        if returnObject is not None:
           
            matrix = returnObject.GetMg()
            if not hierarchyCloneMode:
                if op[ID_CHAMFERGEN_INPUTLINK] is None:
                    matrix = ~genMat * matrix
                pointCount = returnObject.GetPointCount()
                for pointIndex in range(0, pointCount):
                    returnObject.SetPoint(pointIndex, matrix * returnObject.GetPoint(pointIndex))

        if not hierarchyCloneMode:
            returnObject.SetMg(c4d.Matrix())
            returnObject.Message(c4d.MSG_UPDATE)

        if op[ID_CHAMFERGEN_OVERRIDETYPE]:
            TransferSplineMode(returnObject, op)

        return returnObject

    def ChamferSpline(self, startObject, op, pointSelectionName, ignoreFirst, hierarchyCloneMode, hh):
        splineOutputs = []
        settings = c4d.BaseContainer()
        settings[c4d.MDATA_SPLINE_CHAMFERFLAT] = op[ID_CHAMFERGEN_FLAT]
        settings[c4d.MDATA_SPLINE_CHAMFERRADIUS] = op[ID_CHAMFERGEN_RADIUS]
        splineObjList = CollectSplineObjects(startObject, op, ignoreFirst, hierarchyCloneMode, hh)
        if len(splineObjList) == 0:
            return None
        # call edge to spline modeling command
        for splineObj in splineObjList:
            
            foundPoints = False

            if pointSelectionName is not None and pointSelectionName != "":
                foundPoints = ProcessPointSelectionTag(splineObj, pointSelectionName)
            else:                
                foundPoints = ProcessPointSelection(splineObj, math.pi - op[ID_CHAMFERGEN_SELECTIONANGLE])

            optimizeAngle = op[ID_CHAMFERGEN_OPTIMIZEANGLE]
            if optimizeAngle != 0.0:
                OptimizeCollinearPoints(splineObj, math.pi - optimizeAngle)

            if foundPoints:
                res = utils.SendModelingCommand(command=c4d.ID_MODELING_SPLINE_CHAMFER_TOOL,
                                    list=[splineObj],
                                    mode=c4d.MODELINGCOMMANDMODE_POINTSELECTION,
                                    bc=settings,
                                    doc=None)
            if splineObj != None:
                splineObj.Remove()
                OptimizeSpline(splineObj)
                selection = splineObj.GetPointS()
                selection.DeselectAll()
                splineOutputs.append(splineObj)


        if len(splineOutputs) == 0:
            return None
        returnObject = None

        # join the splines if multiple input objects were found
        if len(splineOutputs) > 1:
            doc = op.GetDocument()
            tempdoc = c4d.documents.BaseDocument()
            
            for spline in splineOutputs:
                tempdoc.InsertObject(spline)

            settings[c4d.MDATA_JOIN_MERGE_SELTAGS] = True
            res = utils.SendModelingCommand(command=c4d.MCOMMAND_JOIN,
                                list=splineOutputs,
                                mode=1032176,
                                bc=settings,
                                doc=tempdoc)

            if isinstance(res, list):
                res[0].SetMg(c4d.Matrix())
                returnObject = res[0]
        

        if len(splineOutputs) == 1:
            returnObject = splineOutputs[0]

        genMat = op.GetMg()
        # transform the spline points into generator space. Otherwise cloner has issues cloning
        if returnObject is not None:
           
            matrix = returnObject.GetMg()
            if not hierarchyCloneMode:
                if op[ID_CHAMFERGEN_INPUTLINK] is None:
                    matrix = ~genMat * matrix
                pointCount = returnObject.GetPointCount()
                for pointIndex in range(0, pointCount):
                    returnObject.SetPoint(pointIndex, matrix * returnObject.GetPoint(pointIndex))

        if not hierarchyCloneMode:
            returnObject.SetMg(c4d.Matrix())
            returnObject.Message(c4d.MSG_UPDATE)

        if op[ID_CHAMFERGEN_OVERRIDETYPE]:
            TransferSplineMode(returnObject, op)

        return returnObject

    def GetDDescription(self, node, description, flags):
        # Before adding dynamic parameters, load the parameters from the description resource
        if not description.LoadDescription(node.GetType()):
            return False

        chamfer = node[ID_CHAMFERGEN_MODE] == ID_CHAMFERGEN_CHAMFER
        HideParameter(node, description, ID_CHAMFERGEN_RADIUS, not chamfer)
        HideParameter(node, description, ID_CHAMFERGEN_SELECTIONANGLE, not chamfer)
        HideParameter(node, description, ID_CHAMFERGEN_POINTSELECTION, not chamfer)
        HideParameter(node, description, ID_CHAMFERGEN_FLAT, not chamfer)

        HideParameter(node, description, ID_CHAMFERGEN_DISTANCE, chamfer)
        # After parameters have been loaded and added successfully, return True and DESCFLAGS_DESC_LOADED with the input flags
        return (True, flags | c4d.DESCFLAGS_DESC_LOADED)

    def GetDEnabling(self, node, id, t_data, flags, itemdesc):
        if id[0].id == ID_CHAMFERGEN_SELECTIONANGLE:
            objectLink = node[ID_CHAMFERGEN_INPUTLINK]
            return node[ID_CHAMFERGEN_POINTSELECTION] == "" and (objectLink is None or not objectLink.IsInstanceOf(c4d.Tpointselection))

        if id[0].id == ID_CHAMFERGEN_SPLINETYPE or id[0].id == ID_CHAMFERGEN_SUBDIVISIONS:
            override = node[ID_CHAMFERGEN_OVERRIDETYPE]
            if override == 1:
                return True
            else:
                return False

        return True

    def CheckDirty(self, op, doc):
        inputLink = op[ID_CHAMFERGEN_INPUTLINK]

        usingInputLink = inputLink is not None
        if usingInputLink:
            firstChild = inputLink
        else:
            firstChild = op

        newDirty = CollectChildDirty(firstChild, op, not usingInputLink)
        if self.prevChildDirty != newDirty:
            self.prevChildDirty = newDirty
            op.SetDirty(c4d.DIRTYFLAGS_DATA)

    def GetVirtualObjects(self, op, hh):
        inputLink = op[ID_CHAMFERGEN_INPUTLINK]
        pointSelectionName = op[ID_CHAMFERGEN_POINTSELECTION]

        if inputLink is not None and inputLink.IsInstanceOf(c4d.Tbase):
            if inputLink.IsInstanceOf(c4d.Tpointselection):
                pointSelectionName = inputLink.GetName()
            inputLink = inputLink.GetObject()

        useInputLink = inputLink is not None

        settingsDirty = False

        newDirty = 0
        if not useInputLink:
            newDirty = op.GetDirty(c4d.DIRTYFLAGS_DATA)
        else:
            newDirty = op.GetDirty(c4d.DIRTYFLAGS_DATA | c4d.DIRTYFLAGS_MATRIX)

        if newDirty != self.selfDirtyCount:
            self.selfDirtyCount = newDirty
            settingsDirty = True

        inputDirty = False

        op.NewDependenceList()

        if not useInputLink:
            inputLinkMatrixDirtyNew = 0
            for child in op.GetChildren():
                op.GetHierarchyClone(hh, child, c4d.HIERARCHYCLONEFLAGS_ASSPLINE, inputDirty, None, c4d.DIRTYFLAGS_DATA | c4d.DIRTYFLAGS_MATRIX)
                # matrix dirty buggy yay
                inputLinkMatrixDirtyNew += child.GetDirty(c4d.DIRTYFLAGS_MATRIX) + child.GetHDirty(c4d.HDIRTYFLAGS_OBJECT_MATRIX)
            if inputLinkMatrixDirtyNew != self.inputLinkMatrixDirty:
                inputDirty = True
                self.inputLinkMatrixDirty = inputLinkMatrixDirtyNew
        else:
            selfReferencing = CheckSelfReferencing(inputLink, op)
            if not selfReferencing:
                op.GetHierarchyClone(hh, inputLink, c4d.HIERARCHYCLONEFLAGS_ASSPLINE, inputDirty, None, c4d.DIRTYFLAGS_DATA | c4d.DIRTYFLAGS_MATRIX)
                if not inputDirty:
                    inputLinkMatrixDirtyNew = inputLink.GetDirty(c4d.DIRTYFLAGS_MATRIX) + inputLink.GetHDirty(c4d.HDIRTYFLAGS_OBJECT_MATRIX)
                    if inputLinkMatrixDirtyNew != self.inputLinkMatrixDirty:
                        inputDirty = True
                        self.inputLinkMatrixDirty = inputLinkMatrixDirtyNew
        
        if not inputDirty:
            inputDirty = not op.CompareDependenceList()

        usingInputLink = inputLink is not None

        if not settingsDirty and not inputDirty:
            if not usingInputLink:
                op.TouchDependenceList()
            return op.GetCache(hh)

        firstChild = op.GetDown()

        if firstChild is None and inputLink is None: 
            return c4d.BaseObject(c4d.Onull);
        
        if usingInputLink:
            firstChild = inputLink
        else:
            firstChild = op

        returnObject = None
        if op[ID_CHAMFERGEN_MODE] == ID_CHAMFERGEN_CHAMFER:
            returnObject = self.ChamferSpline(firstChild, op, pointSelectionName, not usingInputLink, not usingInputLink, hh)
        elif op[ID_CHAMFERGEN_MODE] == ID_CHAMFERGEN_OFFSET:
            returnObject = self.OffsetSpline(firstChild, op, not usingInputLink, not usingInputLink, hh)

        if returnObject is not None:
            op.SetDirty(c4d.DIRTYFLAGS_DATA)
            self.selfDirtyCount =  self.selfDirtyCount + 1

            return returnObject

        # nothing was done. Output a dummy nullobj
        return c4d.BaseObject(c4d.Onull)

    def GetContour(self, op, doc, lod, bt):
        if op.GetDeformMode() == False:
            return None

        inputLink = op[ID_CHAMFERGEN_INPUTLINK]
        pointSelectionName = op[ID_CHAMFERGEN_POINTSELECTION]
        firstChild = op.GetDown()

        if inputLink is not None and inputLink.IsInstanceOf(c4d.Tbase):
            if inputLink.IsInstanceOf(c4d.Tpointselection):
                pointSelectionName = inputLink.GetName()
            inputLink = inputLink.GetObject()

        if firstChild is None and inputLink is None: 
            return None;

        usingInputLink = inputLink is not None
        if usingInputLink:
            firstChild = inputLink
        else:
            firstChild = op

        returnObject = None
        if op[ID_CHAMFERGEN_MODE] == ID_CHAMFERGEN_CHAMFER:
            returnObject = self.ChamferSpline(firstChild, op, pointSelectionName, not usingInputLink, False, None)
        elif op[ID_CHAMFERGEN_MODE] == ID_CHAMFERGEN_OFFSET:
            returnObject = self.OffsetSpline(firstChild, op, not usingInputLink, False, None)

        if returnObject is not None:
            returnObject.SetName(op.GetName())
        return returnObject

    def GetBubbleHelp(self, node):
        return "Chamfers a Spline Object and outputs the new version"


if __name__ == "__main__":
    c4d.plugins.RegisterObjectPlugin(id=ID_CHAMFERGEN,
                                     str="Chamfergen",
                                     g=ChamfergenObjectData,
                                     description="opychamfergen",
                                     icon=c4d.bitmaps.InitResourceBitmap(450000043),
                                     info=c4d.OBJECT_GENERATOR | c4d.OBJECT_ISSPLINE | c4d.OBJECT_INPUT)
