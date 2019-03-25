#from pyndn import Face
from pyndn.threadsafe_face import ThreadsafeFace
from pyndn import Name
from pyndn import Interest
from pyndn import Data
from urllib.parse import urlparse
from pyndn.security import KeyChain
from pyndn.security import SafeBag
from pyndn.util import Blob
from pyndn.forwarding_flags import ForwardingFlags
from pyndn.control_parameters import ControlParameters
from pyndn.encoding.tlv_wire_format import TlvWireFormat
from pyndn.node import Node


import pandas as pd
import numpy as np
import types
import signal

import json
import asyncio

PREFIX='/ndn/edu/ucla/%40GUEST/m.krol%40ucl.ac.uk/pinger/'

#the main structure to gather stats
df = pd.DataFrame(columns=['iter', 'src', 'dst', 'status'])
pandasCounter = 0
iterCounter = 1
registeredFaces = set()
faces = {}
loop = ''



async def shutdown(signal, loop):
    print(f'Received exit signal {signal.name}...')

    print('Removing registered prefixes')
    for face in registeredFaces:
        #TODO for now we register one prefix per face, so it works, but it should be changed to read the actual prefixID from a map or sth
        faces[face].removeRegisteredPrefix(1)

    print('Closing database connections')
    #TODO to be replaced by an actual data base
    df.to_csv('stats.csv')

    loop.stop()
    print('Shutdown complete.')


def nfdRegisterPrefix(
  self, registeredPrefixId, prefix, onInterest, onRegisterFailed,
  onRegisterSuccess, flags, commandKeyChain, commandCertificateName, face):
    """
    Do the work of registerPrefix to register with NFD.
        :param int registeredPrefixId: The getNextEntryId() which registerPrefix
      got so it could return it to the caller. If this is 0, then don't add
  to _registeredPrefixTable (assuming it has already been done).
    """
    if commandKeyChain == None:
        raise RuntimeError(
          "registerPrefix: The command KeyChain has not been set. You must call setCommandSigningInfo.")
    if commandCertificateName.size() == 0:
        raise RuntimeError(
          "registerPrefix: The command certificate name has not been set. You must call setCommandSigningInfo.")

    controlParameters = ControlParameters()
    controlParameters.setName(prefix)
    controlParameters.setForwardingFlags(flags)
    controlParameters.setOrigin(65)

    commandInterest = Interest()

    if self.isLocal():
        commandInterest.setName(Name("/localhost/nfd/rib/register"))
        # The interest is answered by the local host, so set a short timeout.
        commandInterest.setInterestLifetimeMilliseconds(2000.0)
    else:
        commandInterest.setName(Name("/localhop/nfd/rib/register"))
        # The host is remote, so set a longer timeout.
        commandInterest.setInterestLifetimeMilliseconds(4000.0)

    # NFD only accepts TlvWireFormat packets.
    commandInterest.getName().append(controlParameters.wireEncode(TlvWireFormat.get()))
    self.makeCommandInterest(
      commandInterest, commandKeyChain, commandCertificateName,
      TlvWireFormat.get())

    # Send the registration interest.
    response = Node._RegisterResponse(
      prefix, onRegisterFailed, onRegisterSuccess, registeredPrefixId, self,
      onInterest, face)
    self.expressInterest(
      self.getNextEntryId(), commandInterest, response.onData,
      response.onTimeout, None, TlvWireFormat.get(), face)


def decomposeName(name):
    src = name.getSubName(13, 1)
    dst = name.getSubName(6, 1)
    seq = name[-1].toSequenceNumber()
    return src, dst, seq


def registerResult(name, status):
    global pandasCounter
    src, dst, seq = decomposeName(name)
    #print("Name:", name, "decomposed into src:", src, "dst:", dst, "iterNumber:", seq)
    #return
    df.loc[pandasCounter] = [seq, src, dst, status]
    pandasCounter += 1


def onData(interest, data):
    print("Received data for interest:", interest.getName())
    registerResult(interest.getName(), 0)

def onTimeout(interest):
    print("Timeoutt", interest.getName())
    registerResult(interest.getName(), 1)

def onNack(interest, nack):
    print("NACK", interest.getName(), "reason", nack.getReason())
    registerResult(interest.getName(), 2)

def test():
    print("test")


def schedulePings():
    global iterCounter

    list_of_pairs = [loop.call_soon(pingFace, f1, f2, iterCounter) for f1 in registeredFaces for f2 in registeredFaces if f1 != f2]
    iterCounter += 1
    loop.call_later(30, schedulePings)



def pingFace(srcFace, dstPrefix, iterNumber):
    print("Will ping from", srcFace, dstPrefix, "iterNumber:", iterNumber)

    face = faces[srcFace]
    name = Name(dstPrefix)
    name.append(Name(srcFace))
    name.appendSequenceNumber(iterNumber)

    #print("name:", name)
    interest = Interest(name)

    face.expressInterest(interest, onData, onTimeout, onNack)


def onInterest(prefix, interest, face, interestFilterId, filter):
    global keyChain
    print("Received an interest:", interest.getName(), "incomingFaceID",  interest.getIncomingFaceId(), "face", face, "interestFilterId", interestFilterId, "prefix", prefix)
    data = Data(interest.getName())
    data.setContent(Blob("Hello from NDN!"))
    keyChain.sign(data, keyChain.getDefaultCertificateName())
    try:
        face.putData(data)
    except Exception as ex:
        print("Error in transport.send: %s", str(ex))

def onRegisterFailed(prefix):
    print("Register failed for prefix " + prefix.toUri())

def onRegisterSuccess(prefix, prefixID):
    print("Register succeded for prefix " + prefix.toUri(), "prefixID:", prefixID)
    registeredFaces.add(prefix)


#load and parse the file with testbed nodes that support fch
hubJson = json.load(open('hubs.json', encoding="utf-8"))
hubList = [ value for value in hubJson.values() if value['fch-enabled'] != False ]

#set up a keyChain
keyChain = KeyChain()
print("Default identity:", keyChain.getDefaultCertificateName())

#main async event loop
loop = asyncio.get_event_loop()

for hub in hubList:
    url = urlparse(hub['site'])
    if(hub['shortname'] not in ['UCLA', 'LIP6']):
        continue

    print("Registering", hub['shortname'], "hostname:", url.hostname)
    face = ThreadsafeFace(loop, url.hostname)
    face.setCommandSigningInfo(keyChain, keyChain.getDefaultCertificateName())
    facePrefix = Name(PREFIX + hub['shortname'])

    print("Face:", facePrefix)
    #shadowing to replace the default PyNDN function that does not support passing options
    # setOrigin(65) must be included to propagate the prefix to other nodes
    face._node._nfdRegisterPrefix = types.MethodType(nfdRegisterPrefix, face._node)
    face.registerPrefix(facePrefix, onInterest, onRegisterFailed, onRegisterSuccess=onRegisterSuccess)
    faces[facePrefix] = face

#schedule pings later, so that prefixes have some time to register and propagate
print("Starting pinging")
loop.call_later(30, schedulePings)

#signal handling for clean shutdown
signals = (signal.SIGHUP, signal.SIGTERM, signal.SIGINT)
for s in signals:
    loop.add_signal_handler(
        s, lambda s=s: loop.create_task(shutdown(s, loop)))



loop.run_forever()

print("~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~FINISHING~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~")
