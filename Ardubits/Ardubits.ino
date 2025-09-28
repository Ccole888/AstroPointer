#include <Wire.h>
#include <Stepper.h>
#include <Adafruit_Sensor.h>
#include <Adafruit_HMC5883_U.h>

//SDA green A4 
//SCL orange A5wX
/* Assign a unique ID to this sensor at the same time */
Adafruit_HMC5883_Unified mag = Adafruit_HMC5883_Unified(12345);

// CW -> 0
// CCW -> 1

float azimuth = 0.0; 
float elevation = 0.0; 

//float vecX = 0.0; 
//float vecY = 0.0;
//float vecZ = 0.0; 

float zGoal; 

const float zeroDegrees = 14; 
const float ninetyDegrees = 42.92; 
const float hundredeightyDegrees = -14; 
const float twoseventyDegrees = -42.55; 

const int motorCCWPin = 7;
const int motorCWPin = 6;

const int zMotorCCWPin = 9;
const int zMotorCWPin = 8; 

void getStuff(); 

void zMotorCW();
void zMotorCCW(); 
void zMotorStart(); 
float degreesToMagnet(float degrees); 
void zMoveMotorGoal(float zGoal, float zDegrees); 

void motorStop();
void motorCCW();
void motorCW();

//#define STEPS 2048
//Stepper stepper(STEPS, 8, 9, 10, 11);
void moveMotorAzmuthGoal(float goal, float heading);
bool goalCompare(float goal, float heading);


void displaySensorDetails(void)
{
  //XY motor pins
  pinMode(motorCCWPin, OUTPUT);
  pinMode(motorCWPin, OUTPUT);

  //z motor pins
  pinMode(zMotorCCWPin, OUTPUT);
  pinMode(zMotorCWPin, OUTPUT);

  sensor_t sensor;
  mag.getSensor(&sensor);
  Serial.println("------------------------------------");
  Serial.print  ("Sensor:       "); Serial.println(sensor.name);
  Serial.print  ("Driver Ver:   "); Serial.println(sensor.version);
  Serial.print  ("Unique ID:    "); Serial.println(sensor.sensor_id);
  Serial.print  ("Max Value:    "); Serial.print(sensor.max_value); Serial.println(" uT");
  Serial.print  ("Min Value:    "); Serial.print(sensor.min_value); Serial.println(" uT");
  Serial.print  ("Resolution:   "); Serial.print(sensor.resolution); Serial.println(" uT");  
  Serial.println("------------------------------------");
  Serial.println("");
  delay(500);
}


void setup(void)
{
  Serial.begin(9600);
  Serial.println("HMC5883 Magnetometer Test"); Serial.println("");
 
  /* Initialise the sensor */
  if(!mag.begin())
  {
    /* There was a problem detecting the HMC5883 ... check your connections */
    Serial.println("Ooops, no HMC5883 detected ... Check your wiring!");
    while(1);
  }
 
  /* Display some basic information on this sensor */
  displaySensorDetails();

  //stepper.setSpeed(15);
}


void loop(void)
{
  if (Serial.available() > 0) {
    //read until terminating character
    String bulkData = Serial.readStringUntil('>'); 

    //delete any extra stuff
    if (bulkdata.startsWith('>')) {
      bulkdata = bulkdata.substring(1); 
    }

    //parse data for all of wanted variables:

    //get index of azimuth section of stuff
    int comma = bulkdata.indexOf(','); 
    azimuth = bulkdata.substring(0, comma).toFloat(); 
    bulkdata = bulkdata.substring(comma + 1); 

    //elevation
    comma = bulkdata.indexOf(','); 
    elevation = bulkdata.substring(0, comma).toFloat(); 
    bulkdata = bulkdata.substring(comma + 1); 

    /*
    //x
    comma = bulkdata.indexOf(','); 
    vecX = bulkdata.substring(0, comma).toFloat(); 
    bulkdata = bulkdata.substring(comma + 1); 

    //y
    comma = bulkdata.indexOf(','); 
    vecY = bulkdata.substring(0, comma).toFloat(); 
    bulkdata = bulkdata.substring(comma + 1); 

    //z
    comma = bulkdata.indexOf(','); 
    vecZ = bulkdata.substring(0, comma).toFloat(); 
    */ 
    
    //print out values: 
    Serial.print("Azimuth: "); 
    Serial.print(azimuth); 
    Serial.print(" | Elevation: "); 
    Serial.println(elevation); 
  }
  /* Get a new sensor event */
  sensors_event_t event;
  mag.getEvent(&event);
 
  //COMPASS STUFF
 
  /* Display the results (magnetic vector values are in micro-Tesla (uT)) */
  Serial.print("X: "); Serial.print(event.magnetic.x); Serial.print("  ");
  Serial.print("Y: "); Serial.print(event.magnetic.y); Serial.print("  ");
  Serial.print("Z: "); Serial.print(event.magnetic.z); Serial.print("  ");Serial.println("uT");

  // Hold the module so that Z is pointing 'up' and you can measure the heading with x&y
  // Calculate heading when the magnetometer is level, then correct for signs of axis.
  float heading = atan2(event.magnetic.y, event.magnetic.x);
 
  // Once you have your heading, you must then add your 'Declination Angle', which is the 'Error' of the magnetic field in your location.
  // Find yours here: http://www.magnetic-declination.com/
  // Mine is: -13* 2' W, which is ~13 Degrees, or (which we need) 0.22 radians
  // If you cannot find your Declination, comment out these two lines, your compass will be slightly off.
  float declinationAngle = 0.22;
  heading += declinationAngle;
 
  // Correct for when signs are reversed.
  if(heading < 0)
    heading += 2*PI;
   
  // Check for wrap due to addition of declination.
  if(heading > 2*PI)
    heading -= 2*PI;
   
  // Convert radians to degrees for readability.
  float headingDegrees = heading * 180/M_PI;

 
 
  Serial.print("Heading (degrees): "); Serial.println(headingDegrees);

  //MOTOR STUFF XY MOVEMENT
  if(!goalCompare(azimuth, headingDegrees)){
   moveMotorAzmuthGoal(azimuth, headingDegrees);
  }
  else {
    Serial.println("XY Goal Met!");
    motorStop();
  }
 
  zGoal = degreesToMagnet(elevation); 

  if(!goalCompare(zGoal, event.magnetic.z)) {
    zMoveMotorGoal(zGoal, event.magnetic.z);
    Serial.print("Z goal: "); 
    Serial.println(zGoal);
  }
  else {
    Serial.println("Z Goal met"); 
    zMotorStop(); 
  }
 
  
  Serial.println(""); 
  delay(500);
}

bool goalCompare(float goal, float heading){
  float headingPlus = heading + 5;
  /*x
  if(headingPlus > 359.99){
    headingPlus = headingPlus - 360;
  }
  */
  float headingMinus = heading - 5;
  /*
  if(headingMinus < 0){
    headingMinus = headingMinus + 360;
  }
  */
  /*
  Serial.print("Range: " );
  Serial.print(headingMinus);  
  Serial.print(" : "); 
  Serial.println(headingPlus);
  //Serial.println(headingPlus);
  */ 
 
  if((goal < headingPlus)&&(goal > headingMinus)){
    Serial.println("Goal met!"); 
    return true;
  }
  else{
    Serial.print(goal);
    Serial.println(": Not met"); 
    return false;
  }

  Serial.println(""); 
}


void moveMotorAzmuthGoal(float goal, float heading){
  float oppositeHeading = heading + 180;
  if(oppositeHeading > 359){
    oppositeHeading = oppositeHeading - 360;
  }
  if(heading < 180){
    if(goal > heading){
      if(goal > oppositeHeading){
        //turn CW
        //Serial.println("CW");
        //stepper.step(50);
        motorCW();
      }
      if(goal < oppositeHeading){
        //turn CCW
        //Serial.println("CCW");
        //stepper.step(-50);
        motorCCW();
      }
    }
    //goal will then be less than heading
    else if(goal < heading){
      if(goal > oppositeHeading){
        //turn CCW
        //Serial.println("CCW");
        //stepper.step(-50);
        motorCCW();
      }
      if(goal < oppositeHeading){
        //turn CW
        //Serial.println("CW");
        //stepper.step(50);
        motorCW();
      }
    }
  }
  else{
    if(goal > heading){
      if(goal > oppositeHeading){
        //turn CCW
        Serial.println("CCW");
        //stepper.step(-50);
        motorCCW();
      }
      if(goal < oppositeHeading){
        //turn CW
        Serial.println("CW");
        //stepper.step(50);
        motorCW();
      }
    }
    //goal will then be less than heading
    else if(goal < heading){
      if(goal > oppositeHeading){
        //turn CW
        //Serial.println("CW");
        //stepper.step(50);
        motorCW();
      }
      if(goal < oppositeHeading){
        //turn CCW
        //Serial.println("CCW");
        //stepper.step(-50);
        motorCCW();
      }
    }
  }
}

void motorCW(){
  Serial.println("XY-CW");
  digitalWrite(motorCCWPin, LOW);
  digitalWrite(motorCWPin, HIGH);
}

void motorCCW(){
  Serial.println("XY-CCW");
  digitalWrite(motorCCWPin, HIGH);
  digitalWrite(motorCWPin, LOW);
}

void motorStop(){
  digitalWrite(motorCCWPin, LOW);
  digitalWrite(motorCWPin, LOW);
}

void zMotorCW(){
  Serial.println("Z-CW");
  digitalWrite(zMotorCCWPin, LOW);
  digitalWrite(zMotorCWPin, HIGH);
}

void zMotorCCW(){
  Serial.println("Z-CCW");
  digitalWrite(zMotorCCWPin, HIGH);
  digitalWrite(zMotorCWPin, LOW);
}

void zMotorStop(){
  digitalWrite(zMotorCCWPin, LOW);
  digitalWrite(zMotorCWPin, LOW);
}

float degreesToMagnet(float degrees) {
  //First make it the absolute value of degrees
  float newDegrees = 0; 
  if(degrees < 0) {
    degrees = degrees + 360; 
  }

  if((degrees >= 0) && (degrees <= 90)) {
    newDegrees = map(degrees, 0, 90, zeroDegrees, ninetyDegrees); 
  }
  else if((degrees > 90) && (degrees < 180)) {
    newDegrees = map(degrees, 90, 180, ninetyDegrees, hundredeightyDegrees);
  }
  else if((degrees >= 180) && (degrees <= 270)) {
    newDegrees = map(degrees, 180, 270, hundredeightyDegrees, twoseventyDegrees); 
  }
  else if ((degrees > 270) && (degrees <= 360)) {
    newDegrees = map(degrees, 270, 360, twoseventyDegrees, zeroDegrees); 
  }

  Serial.print("Degrees: "); 
  Serial.print(degrees); 
  Serial.print(" NewDegrees: ");
  Serial.println(newDegrees); 

  return newDegrees;

  //degrees = map(degrees, fromLow, fromHigh, toLow, toHigh); 
}

void zMoveMotorGoal(float zGoal, float zDegrees) {
  float posGoal = zGoal; 
  if (zGoal < 0) {
    posGoal = zGoal * -1; 
  } 

  float posDegrees = zDegrees; 
    if (zDegrees < 0) {
    posGoal = zDegrees * -1; 
  } 
  if((posGoal - posDegrees) < 0) {
    //current position is greater than goal, therefore 
    zMotorCW();
  } 
  else {
    //current position is less than goal
    zMotorCCW(); 
  }
  
}
