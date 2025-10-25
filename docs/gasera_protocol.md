
## AK protocol **format** as used by the GASERA ONE

1) The AK request **format** (Client to GASERA ONE) is as follow:
```
<STX><BLANK><FUNC_BYTE1><FUNC_BYTE2><FUNC_BYTE3><FUNC_BYTE4><BLANK>K<channel><BLANK>
<DATA_BYTE1><DATA_BYTE2>..<DATA_BYTE_N><ETX> (STX=ASCII 02, ETX=ASCII 03)
```
2) The AK response **format** (GASERA ONE to Client) is as follow:
```
<STX><BLANK><FUNC_BYTE1><FUNC_BYTE2><FUNC_BYTE3><FUNC_BYTE4><BLANK>
<error_status_byte><BLANK><DATA_BYTE1><DATA_BYTE2>..<DATA_BYTE_N><ETX> (STX=ASCII 02, ETX=ASCII 03)
```
In the above, BLANK refers to single space. The error status byte in the response is set to 0 on success; in case of request processing error the error status is set to 1.
Supported commands are given in the next section.


## Supported commands


### Ask Current Device Status – ASTS

**Available from MW ver**. 1.3.9
a. **format** ASTS K0 - request the current device status
```
response ASTS <**errorstatus**> <device_status> (**errorstatus**: 0=no errors, 1=error)
```
**Possible values** for device_status:
- 0 – device initializing
- 1 – initialization error
- 2 – device idle state
- 3 – device self-test in progress
- 4 – malfunction
- 5 – measurement in progress
- 6 – calibration in progress
- 7 – canceling measurement
- 8 – laserscan in progress


### Ask Active Errors – AERR

**Available from MW ver**. 1.3.9
a. **format** AERR K0 - ask the current list of active error codes (empty data part if no errors)
```
response (success) AERR 0 <err_code1> <err_code2> <err_codeN> ..
```
```
response (request error) AERR 1
```


### Ask Task List – ATSK

**Available from MW ver**. 1.3.9
b. **format** ATSK K0 - request the current list of measurement tasks
```
response (success) ATSK 0 <taskid> <taskname> <taskid> <taskname> ..
```
```
response (error) ATSK 1
```


### Start New Measurement – STAM

**Available from MW ver**. 1.3.9
c. **format** STAM K0 <taskId> - start measurement based on task with specified id (id of tasks is **retrieve**d from response to Ask Task List request)
```
response STAM <**errorstatus**> (0=no errors, 1=error)
```


### Stop Current Measurement – STPM

**Available from MW ver**. 1.3.9
d. **format** STPM K0
```
response STPM <**errorstatus**> (0=no errors, 1=error)
```


### Get Last Measurement Results (concentrations) – ACON

**Available from MW ver**. 1.3.9
e. **format** ACON K0
```
response (success): ACON 0 <timestamp> <cas> <conc_ppm> <timestamp> <cas> <conc_ppm> ..
```
```
response (error) ACON 1
```
If MW database version is 10 or earlier, the timestamp is the time and date values when the measurement result was calculated. If MW database version is newer 10, the timestamp corresponds to the sampling time or time of the gas exchange.
Timestamp is defined using internal clock of GASERA ONE unit. It can be changed only via user interface.
The timestamp is in Linux (epoch) **format**, i.e., number of seconds elapsed since 1.1.1970.
**Format**ting of the ACON command response can be changed using the SCON command.


### Set measurement component (CAS) order – SCOR

**Available from MW ver**. 1.6.0
The order of data elements is based on CAS codes of gas components. The order can be changed by using the SCOR command. If the SCOR command has not been invoked, the elements are ordered automatically by GASERA ONE.
f. **format** SCOR K0 <CAS_1> <CAS_2> … <CAS_n>
```
response (success): SCOR 0
```
```
response (error) SCOR 1
```
Set the order of in which component CAS elements are returned when asking for the last measurement results using the ACON command, i.e., ACON data elements are ordered by CAS in the order specified by SCOR command.
The SCOR command is active until the device is reboot, i.e., after device reboot the command needs to be re-invoked prior to starting measurement.


### Set concentration settings (**format**) – SCON

**Available from MW ver**. 1.7.3
g. **format** SCON K0 <**format** bits> (0/1 (show time) 0/1 (show CAS) 0/1 (show concentration) 0/1 (show gas inlet)
```
response (success): SCON 0
```
```
response (error) SCON 1
```
Set the **format** of the ACON response. The **format** is specified as bit pattern. e.g., command SCON K0 0 0 1 0 means show only concentration values in ppm.
The command is active until device is rebooted, or SCON is called with new bit pattern value. The last bit (inlet) is optional and requires MW version 1.8.2 or newer.


### Get Measurement Status (Phase) – AMST

**Available from MW ver**. 1.5.0
h. **format** AMST K0
```
response AMST <**errorstatus**> <measurement status> (**errorstatus**: 0=no errors, 1=error)
```
**Possible values** of measurement status:
- 0 – none (device is idle)
- 1 – gas exchange in progress
- 2 – sample integration (measurement) in progress
- 3 – sample analysis in progress
- 4 – laser tuning in progress


### Get Device Name – ANAM

**Available from MW ver**. 1.5.0
```
**format** ANAM K0
```
```
response ANAM <**errorstatus**> <device name string> (**errorstatus**: 0=no errors, 1=error)
```
**Returns** the device name string (if set). Empty value if not set.


### Start new measurement (by task name) – STAT

**Available from MW ver**. 1.7.3
j. **format** STAT K0 <task name>
```
response STAT <**errorstatus**> (**errorstatus**: 0=no errors, 1=error)
```
Start a new measurement based on the specified task. Alternative to STAM, but parameter is task name instead of internal task id.


### Get current measurement iteration number – AITR

**Available from MW ver**. 1.7.2
k. **format** AITR K0
```
response AITR <**errorstatus**> <iteration number> (**errorstatus**: 0=no errors, 1=error)
```
Request the current measurement iteration number. In MW version 1.7.2 or 1.7.3, the returned value is the internal (global) measurement iteration number from the internal database. In MW version 1.8.2 or newer, AITR **returns** the zero-based iteration number within the currently in-progress measurement (starts from zero when a new measurement is started).


### Get current device network settings – ANET

**Available from MW ver**. 1.8.7
l. **format** ANET K0
```
response ANET <**errorstatus**> <useDHCP> <ip address> <netmask> <gateway>
```
**errorstatus**: 0=no errors, 1=error
usDHCP: 0/1 (DHCP not in use / in use)
ip address: current IP address (NO_IP if not available)
netmask: netmask IP (NO_NETMASK if not available)
gateway: gateway IP (NO_GW if not available)
Request the current network settings for the device.


### Set device network settings – SNET

**Available from MW ver**. 1.8.7
m. **format** SNET K0 <useDHCP> <ip address> <netmask> <gateway>
```
response SNET <**errorstatus**> (**errorstatus**: 0=no errors, 1=error)
```
**Request to** set the device network settings. All parameters are required. For example, to set device to use DHCP, set useDHCP parameter to 1, ip to NO_IP, netmask to NO_NETMASK and gateway to NO_GW.
In case IP should not be set, set ip address to NO_IP.
In case netmask should not be set, set netmask to NO_NETMASK.
In case gateway should not be set, set gatway to NO_GW.
**NOTE:** To make network setting changes effective, restart of the analyzer is required.


### Get device parameter value – APAR

**Available from MW ver**. 1.8.9
n. **format** APAR K0 <parameter name>
```
response APAR <**errorstatus**> <parameter value> (**errorstatus**: 0=no errors, 1=error)
```
Request value of device parameter, such as cell temperature or heater power. The response contains the parameter value only on success (**errorstatus** 0). The command **returns** error status 1, for example, in case the specified parameter name does not exist. Parameter name is case insensitive.
**Examples of parameter names**: CELLTEMP (temperature of PA gas cell), VAISALACO2VALUE (CO2 value provided by Vaisala sensor, if assembled to GASERA ONE analyzer)


### Set Online Measurement Mode – SONL

**Available from MW ver**. 2.0.1
o. **format** SONL K0 <enable (1) / disable (0)>
```
response SONL <**errorstatus**> (**errorstatus**: 0=no errors, 1=error)
```
Set device online measurement mode. In case, online mode is enabled (1), no measurement results are stored in the device internal database in order to save space.


### Get current device date and time – ACLK

**Available from MW ver**. 2.0.2
p. **format** ACLK K0
```
response ACLK <**errorstatus**> <date/time string>
```
Return the current device date and time in the **format**: YYYY-mm-ddThh:mm:ss. Device uses internally UTC time zone. Time can be set via user interface only.


### Set Laser Tuning Interval – STUN

**Available from MW ver**. 2.0.2
q. **format** STUN K0 <interval value>
```
response STUN <**errorstatus**> (**errorstatus**: 0=no errors, 1=error)
```
Set the interval / frequency value on-demand for laser tuning for laser-type devices (QCL/DFB) (overriding default value from GASERA ONE internal setting in init). **Possible values**:
- K0 = 0 – do not tune
- K0 = 1 – tune every iteration
- K0 > 1 – tune every Nth iteration.
The value is used until a new STUN command is received, or a new measurement is started (on new measurement start, the default value from init is assigned).


### Get Measurement Task Parameters – ATSP

**Available from MW ver**. 2.4.0
r. **format** ATSP K0 <measurement task id>
```
response ATSP <**errorstatus**> <CompCAS1,CompCAS2,..,CompCASn>
```
<TargetPressure> <Flush Time Bypass> <Flush Time Cell>
<Cell Flush Cycles>
(**errorstatus**: 0=no errors, 1=error)
**Retrieve** the list of parameters for the specified measurement task: list of measured component CAS, target pressure, flush time bypass, flush time cell, and cell flush cycles.


### Get System Parameters List – ASYP

**Available from MW ver**. 2.4.0
s. **format** ASYP K0
```
response ASYP <**errorstatus**> <param1_name>,<param1_value>,<param1_min>,<param1_max>,<param1_unit> <param2_name>,…
```
(**errorstatus**: 0=no errors, 1=error)
**Retrieve** the list of device system parameters (parameter name, value, min. value, max. value and unit).


### Get Multi-Point Sampler Parameters – AMPS

**Available from MW ver**. 2.4.0
t. **format** AMPS K0
```
response AMPS <**errorstatus**> <inlet-id> <active(0/1)> <byPassTimeSecs> <inlet_id>…
```
(**errorstatus**: 0=no errors, 1=error, 2=request ok / MPS not connected)
**Retrieve** the inlet configuration for the Multi-Point Sampler (if available / connected).


### Get Device In**format**ion – ADEV

**Available from MW ver**. 2.4.0
u. **format** ADEV K0
```
response ADEV <**errorstatus**> <Manufacturer> <Serial Number> <Device Name>
```
<Firmware version>
(**errorstatus**: 0=no errors, 1=error)
**Retrieve** general device in**format**ion, such as manufacturer, serial number, and firmware version. Response fields are surrounded by double quotes. In case some field in the response is not available, an empty string is returned.


### Start Device Self-Test – STST

**Available from MW ver**. 2.4.0
```
**format** STST K0
```
```
response STST <**errorstatus**>
```
(**errorstatus**: 0=no errors, 1=error)
**Request to** start device self-test routine. Returned **errorstatus** field indicates request status. The self-test routine result / state can be subsequently queried with the AK-command ASTR (Get device self-test result).


### Get Device Self-Test Result – ASTR

**Available from MW ver**. 2.4.0
w. **format** ASTR K0
```
response ASTR <**errorstatus**> <self-test state/result>
```
(**errorstatus**: 0=no errors, 1=error)
Request device self-test result / state. If the request is processed successfully, error status **returns** 0, otherwise 1. The self-test state/result field is interpreted as follows:
-2 = test result N/A (e.g., self-test routine has not been started)
-1 = test in progress
0 = self-test failed
1 = self-test completed successfully


### Reboot device – RDEV

**Available from MW ver**. 2.4.0
```
**format** RDEV K0
```
```
response RDEV <**errorstatus**>
```
(**errorstatus**: 0=no errors, 1=error)
**Request to** reboot the measurement device. After the success status is received, device reboots after approx. 2 seconds. **NOTE:** use caution when using this command, as the device is rebooted in any state (e.g., even though a measurement is in progress).


## Examples of using the AK protocol



### Example requests and responses

Examples of typical usage of the AK communication protocol are presented in this section. Screen shot of examples is given in the next section. Numbers within brackets in example requests and responses refer to line numbers in screen shot in the next section.
We can query the current device state using the following command
```
Request: <STX> ASTS K0 <ETX> [9]
```
```
Response: <STX> ASTS 0 5<ETX> [10], which indicates device is measuring.
```
To start a measurement with the GASERA ONE, a measurement task must be selected. Measurement tasks are created using the user interface of the GASERA ONE.
A list of measurement tasks can be requested with the Ask Task List command. The response will contain the task list (each data element is composed of the measurement task name and its internal task id). To start a measurement, we need to know the task id.
```
Request: <STX> ATSK K0 <ETX> [1]
```
```
Example response: <STX> ATSK 0 7 Calibration task 11 TEST<ETX> [2]
```
In the above example two tasks are returned, Calibration task with task id 11, and TEST with task id 11.
```
Request: <STX> SCOR K0 74-82-8 124-38-9 7732-18-5 630-08-0 10024-97-2 7664-41-7 7446-09-5<ETX>
```
```
Example response: <STX> SCOR 0 <ETX>
```
The above request specifies the order of components (CAS) when requesting last measurement results using ACON, i.e., 74-82-8 (CH4), 124-38-9 (CO2), 7732-18-5 (H2O), 630-08-0 (CO), 10024-97-2 (N2O), 7664-41-7 (NH3) and 7446-09-5 (SO2).
If the user wants to start a measurement using the above TEST task, the Start New Measurement command should be sent.
```
Request: <STX> STAM K0 11 <ETX> [6]
```
```
Example response: <STX> STAM 0 <ETX> [7] (0 status indicates success, 1 indicates some error condition)
```
Current measurement results can be requested using the Get Last Measurement Results command.
```
Request: <STX> ACON K0 <ETX> [15]
```
Example response:
<STX> ACON 0 1511865967 74-82-8 0.919439 1511865967 124-38-9 435.765 1511865967 7732-18-5 7125.4 1511865967 630-08-0 0 1511865967 10024-97-2 0 1511865967 7664-41-7 0.0044561 1511865967 7446-09-5 0<ETX> [16]
Using the timestamp field (time in Unix epoch), it is possible to determine when results have been updated. Successive calls will return equal timestamps and result values until the next measurement is complete and new results are available from the analyzer. In the above example response, we can interpret that the component with CAS value 74-82-8 (CH4) has concentration value 0.919439 ppm (at Unix epoch time 1511865967) etc.
The measurement can be stopped at any time using the Stop Current Measurement command. Stopping the measurement corresponds to similar action triggered from user interface of GASERA ONE.
```
Request: <STX> STPM K0 <ETX> [18]
```
```
Example response: <STX> STPM 0 <ETX> [19]
```
Device error state can be requested by using the following AK request:
```
Request: <STX> AERR K0 <ETX> [4]
```
```
Example response: <STX> AERR 0 8001<ETX> [5]
```
This indicates that error code 8001 is currently active. List of most common error codes is in the GASERA ONE User manual. The complete error code list is in GASERA ONE Service manual.

---

## 🔗 Resources

- GASERA ONE AK Protocol-rev_h
