"""
This module takes care of starting the API Server, Loading the DB and Adding the endpoints
"""
import os
from flask import Flask, request, jsonify, url_for, send_from_directory
from flask_migrate import Migrate
from flask_swagger import swagger
import requests
from api.utils import APIException, generate_sitemap
from api.models import db, User, Patient, Doctor, Speciality, Medical_Appointment, Alergic, Medicated
from api.admin import setup_admin
from api.commands import setup_commands
from flask_bcrypt import Bcrypt
from flask_jwt_extended import create_access_token
from flask_jwt_extended import get_jwt_identity
from flask_jwt_extended import jwt_required
from flask_jwt_extended import JWTManager
from flask_cors import CORS, cross_origin
from flask_mail import Mail, Message
from datetime import datetime, time, timedelta
from api.models import DoctorAvailability
import uuid





# from models import Person

ENV = "development" if os.getenv("FLASK_DEBUG") == "1" else "production"
static_file_dir = os.path.join(os.path.dirname(
    os.path.realpath(__file__)), '../public/')
app = Flask(__name__)


app.config.update(dict(
    DEBUG=False,
    MAIL_SERVER='smtp.gmail.com',
    MAIL_PORT=587,
    MAIL_USE_TLS=True,
    MAIL_USE_SSL=False,
    MAIL_USERNAME="mediconecta1@gmail.com",
    MAIL_PASSWORD= os.getenv("MAIL_PASSWORD")
))

mail= Mail(app)

CORS(app)
app.url_map.strict_slashes = False

# Setup the Flask-JWT-Extended extension
app.config["JWT_SECRET_KEY"] = "super-secret"  # Change this!
jwt = JWTManager(app)

#Bcrypt
bcrypt = Bcrypt(app)


# database condiguration
db_url = os.getenv("DATABASE_URL")
if db_url is not None:
    app.config['SQLALCHEMY_DATABASE_URI'] = db_url.replace(
        "postgres://", "postgresql://")
else:
    app.config['SQLALCHEMY_DATABASE_URI'] = "sqlite:////tmp/test.db"

app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
MIGRATE = Migrate(app, db, compare_type=True)
db.init_app(app)

# add the admin
setup_admin(app)

# add the admin
setup_commands(app)

# Add all endpoints form the API with a "api" prefix
#app.register_blueprint(api, url_prefix='/api')

# Handle/serialize errors like a JSON object


@app.errorhandler(APIException)
def handle_invalid_usage(error):
    return jsonify(error.to_dict()), error.status_code

# generate sitemap with all your endpoints


@app.route('/')
def sitemap():
    if ENV == "development":
        return generate_sitemap(app)
    return send_from_directory(static_file_dir, 'index.html')

# any other endpoint will try to serve it like a static file


@app.route('/<path:path>', methods=['GET'])
def serve_any_other_file(path):
    if not os.path.isfile(os.path.join(static_file_dir, path)):
        path = 'index.html'
    response = send_from_directory(static_file_dir, path)
    response.cache_control.max_age = 0  # avoid cache memory
    return response

#Register admin users    
@app.route("/api/register/user", methods=["POST"])
def register_user():
    body = request.get_json(silent=True)
    
    if body is None:
        return jsonify({'msg': "Debes enviar info al body"}), 400
    if 'email' not in body:
        return jsonify({'msg': "El campo email es obligatorio"}), 400
    if 'password' not in body:
        return jsonify({'msg': "El campo password es obligatorio"}), 400
    
    new_user = User()
    new_user.name = body.get('name')  # Usar get() en lugar de indexación directa para evitar errores si 'name' no está en el cuerpo
    new_user.email = body['email']
    pw_hash = bcrypt.generate_password_hash(body['password']).decode('utf-8')
    new_user.password = pw_hash
    new_user.is_active = True
    db.session.add(new_user)
    db.session.commit()

    
    return jsonify({"message": "User registered successfully"}), 201


# Login Admin Users
@app.route("/api/login/user", methods=["POST"])

def create_admin_login():
    body = request.get_json (silent = True)
    
    if body is None:
        return jsonify({'msg': "Debe enviar info al body"}), 400
    if 'email' not in body:
        return jsonify({'msg': "El campo email es obligatorio"}), 400
    if 'password' not in body:
        return jsonify({'msg': "El campo password es obligatorio"}), 400
    # Fetch user from database
    user = User.query.filter_by(email=body["email"]).first()
    #Check if user exists
    if user is None:
        return jsonify({"msg": "Bad username"}), 401
    #devuelve TRUE si la contraseña es correcta
    password_correct = bcrypt.check_password_hash(user.password, body['password'])
    if not password_correct:
        return jsonify({"msg":"Wrong password"}), 401
    # Generate token
    access_token = create_access_token(identity=user.email)
    print(user)
    return jsonify({'msg': 'Login succesfull...',
                    'token': access_token})

#GET Admin Users
@app.route('/users', methods=['GET'])
def get_users():
    users = User.query.all()

    users_serialized = []
    for user in users:
        users_serialized.append(user.serialize())

    response_body = {
        "msg": "ok",
        "result": users_serialized
    }

    return jsonify(response_body), 200

#GET Admin User by id
@app.route('/user/<int:user_id>', methods=['GET'])
def get_user(user_id):
    user = User.query.get(user_id)
    if user:
        user_data = {
            "id": user.id,
            "name": user.name,
            "email": user.email,
        }
        return jsonify({"message": "User founded", "user": user_data}), 200
    return jsonify({"message": "User not found"}), 404

#PUT Admin user by id
@app.route('/user/<int:user_id>', methods=['PUT'])
def update_user(user_id):
    user = User.query.get(user_id)
    if user:
        data = request.json
        user.email = data.get('email', user.email)
        user.password = data.get('password', user.password)
        user.is_active = data.get('is_active', user.is_active)
        db.session.commit()
        return jsonify({"message": "User updated"}), 200
    return jsonify({"message": "User not found"}), 404

#DELETE Admin user by id
@app.route('/user/<int:user_id>', methods=['DELETE'])
def delete_user(user_id):
    user = User.query.get(user_id)
    if user:
        db.session.delete(user)
        db.session.commit()
        return jsonify({"message": "User deleted"}), 200
    return jsonify({"message": "User not found"}), 404


#Register Patients
@app.route("/api/register/patient", methods=["POST"])
def register_patient():
    body = request.get_json(silent=True)
    if body is None:
        return jsonify({'msg': "Debes enviar info al body"}), 400
    if 'email' not in body or 'password' not in body:
        return jsonify({'msg': "Los campos email y password son obligatorios"}), 400
    
    # Convertir las cadenas "true" o "false" a booleanos
    # alergic_bool = body['alergic'].lower() == "true"
    # medicated_bool = body['medicated'].lower() == "true"
    
    new_patient = Patient()
    new_patient.name = body['name']
    new_patient.surname = body['surname']
    # new_patient.age = int(body['age'])
    # new_patient.identification = body['identification']
    # new_patient.social_security = body['social_security']
    new_patient.email = body['email']
    pw_hash = bcrypt.generate_password_hash(body['password']).decode('utf-8')
    new_patient.password = pw_hash
    # new_patient.alergic = alergic_bool
    # new_patient.medicated = medicated_bool
    new_patient.is_active = True

    db.session.add(new_patient)
    db.session.commit()
    return jsonify({"message": "Patient registered successfully"}), 201

# Login Patient
@app.route("/api/login/patient", methods=["POST"])

def create_login():
    body = request.get_json (silent = True)
    
    if body is None:
        return jsonify({'msg': "Debe enviar info al body"}), 400
    if 'email' not in body:
        return jsonify({'msg': "El campo email es obligatorio"}), 400
    if 'password' not in body:
        return jsonify({'msg': "El campo password es obligatorio"}), 400
    # Fetch user from database
    patient = Patient.query.filter_by(email=body["email"]).first()
    #Check if user exists
    if patient is None:
        return jsonify({"msg": "Bad username"}), 401
    #devuelve TRUE si la contraseña es correcta
    password_correct = bcrypt.check_password_hash(patient.password, body['password'])
    if not password_correct:
        return jsonify({"msg":"Wrong password"}), 401
    # Generate token
    access_token = create_access_token(identity=patient.email)
    print(patient)
    return jsonify({'msg': 'Login succesfull...',
                    'token': access_token,
                    'patient': patient.serialize()})

#GET Patients
@app.route('/patients', methods=['GET'])
def get_patients():
    patients = Patient.query.all()

    patients_serialized = []
    for patient in patients:
        patients_serialized.append(patient.serialize())

    response_body = {
        "msg": "ok",
        "result": patients_serialized
    }

    return jsonify(response_body), 200

#GET Patient by id
@app.route('/patient/<int:patient_id>', methods=['GET'])
def get_patient(patient_id):
    patient = Patient.query.get(patient_id)
    if patient:
        patient_data = {
            "id": patient.id,
            "name": patient.name,
            "surname": patient.surname,
            "age": patient.age,
            "identification": patient.identification,
            "social_security": patient.social_security,
            "email": patient.email,
            "alergic": patient.alergic,
            "specific_alergic": patient.specific_alergic,
            "medicated": patient.medicated,
            "specific_medicated": patient.specific_medicated,
            "is_active": patient.is_active
        }
        return jsonify({"message": "Patient found", "patient": patient_data}), 200
    return jsonify({"message": "Patient not found"}), 404

#PUT Patient by id
@app.route('/patient/<int:patient_id>', methods=['PUT'])
def update_patient(patient_id):
    patient = Patient.query.get(patient_id)
    if not patient:
        return jsonify({"message": "Patient not found"}), 404
    
    # Actualizar los campos del paciente según los datos proporcionados en la solicitud
    data = request.json
    patient.name = data.get('name', patient.name)
    patient.surname = data.get('surname', patient.surname)
    patient.age = data.get('age', patient.age)
    patient.identification = data.get('identification', patient.identification)
    patient.social_security = data.get('social_security', patient.social_security)
    patient.email = data.get('email', patient.email)
    patient.alergic = data.get('alergic', patient.alergic)
    patient.specific_alergic = data.get('specific_alergic', patient.specific_alergic)
    patient.medicated = data.get('medicated', patient.medicated)
    patient.specific_medicated = data.get('specific_medicated', patient.specific_medicated)
    patient.is_active = data.get('is_active', patient.is_active)
    
    db.session.commit()
    
    return jsonify({"message": "Patient updated successfully"}), 200

#DELETE Patient by id
@app.route('/patient/<int:patient_id>', methods=['DELETE'])
def delete_patient(patient_id):
    patient = Patient.query.get(patient_id)
    if not patient:
        return jsonify({"message": "Patient not found"}), 404
    
    db.session.delete(patient)
    db.session.commit()
    
    return jsonify({"message": "Patient deleted successfully"}), 200

#Register doctors    
@app.route("/api/register/doctor", methods=["POST"])
def register_doctor():
    body = request.get_json(silent=True)
    
    if body is None:
        return jsonify({'msg': "Debes enviar info al body"}), 400
    if 'email' not in body:
        return jsonify({'msg': "El campo email es obligatorio"}), 400
    if 'password' not in body:
        return jsonify({'msg': "El campo password es obligatorio"}), 400
    
    new_doctor = Doctor()
    new_doctor.name = body['name']
    new_doctor.surname = body['surname']
    new_doctor.email = body['email']
    pw_hash = bcrypt.generate_password_hash(body['password']).decode('utf-8')
    new_doctor.password = pw_hash
    new_doctor.is_active = True

    # Verificar si el email ya está registrado
    existing_doctor = Doctor.query.filter_by(email=new_doctor.email).first()
    if existing_doctor:
        return jsonify({'msg': "El email ya está registrado"}), 400

    # Guardar el nuevo doctor en la base de datos
    db.session.add(new_doctor)
    db.session.commit()

    # Crear una instancia de DoctorAvailability usando el id del nuevo doctor por dia
    default_availability = DoctorAvailability(
         doctor_id=new_doctor.id,  # Aquí pasamos el id del nuevo doctor
         day_of_week=0,  # por defecto para el domingo
         start_time=time(hour=9, minute=0),  # empezando a las 9:00 AM
         end_time=time(hour=17, minute=0)    # terminando a las 5:00 PM
     )

    # default_availability = DoctorAvailability(
    #      doctor_id=new_doctor.id,  # Aquí pasamos el id del nuevo doctor
    #      day_of_week=1,  # por defecto para el domingo
    #      start_time=time(hour=9, minute=0),  # empezando a las 9:00 AM
    #      end_time=time(hour=17, minute=0)    # terminando a las 5:00 PM
    #  )

    # default_availability = DoctorAvailability(
    #      doctor_id=new_doctor.id,  # Aquí pasamos el id del nuevo doctor
    #      day_of_week=2,  # por defecto para el domingo
    #      start_time=time(hour=9, minute=0),  # empezando a las 9:00 AM
    #      end_time=time(hour=17, minute=0)    # terminando a las 5:00 PM
    #  )

    # default_availability = DoctorAvailability(
    #      doctor_id=new_doctor.id,  # Aquí pasamos el id del nuevo doctor
    #      day_of_week=3,  # por defecto para el domingo
    #      start_time=time(hour=9, minute=0),  # empezando a las 9:00 AM
    #      end_time=time(hour=17, minute=0)    # terminando a las 5:00 PM
    #  )

    # default_availability = DoctorAvailability(
    #      doctor_id=new_doctor.id,  # Aquí pasamos el id del nuevo doctor
    #      day_of_week=4,  # por defecto para el domingo
    #      start_time=time(hour=9, minute=0),  # empezando a las 9:00 AM
    #      end_time=time(hour=17, minute=0)    # terminando a las 5:00 PM
    #  )


     # Crear una instancia de DoctorAvailability para cada día de la semana
    #  for day_of_week in range(5):  # Recorre de 0 a 4 para representar de lunes a viernes
    #      # Crear una instancia de DoctorAvailability para el día actual
    #      default_availability = DoctorAvailability(
    #          doctor_id=new_doctor.id,  # Aquí pasamos el id del nuevo doctor
    #          day_of_week=day_of_week,  # Día de la semana actual en la iteración
    #          start_time=time(hour=9, minute=0),  # empezando a las 9:00 AM
    #          end_time=time(hour=17, minute=0)    # terminando a las 5:00 PM
    #      )

    
    

    # Verificar si el horario de disponibilidad ya está ocupado
    existing_availability = DoctorAvailability.query.filter_by(
        doctor_id=new_doctor.id,
        day_of_week=default_availability.day_of_week,
        start_time=default_availability.start_time,
        end_time=default_availability.end_time
    ).first()

    if existing_availability:
        return jsonify({'msg': "El horario de disponibilidad ya está ocupado"}), 400

    # Guardar la disponibilidad del doctor en la base de datos
    db.session.add(default_availability)
    db.session.commit()

    return jsonify({"message": "Doctor registered successfully"}), 201



# Login Doctors
@app.route("/api/login/doctor", methods=["POST"])

def create_doctor_login():
    body = request.get_json (silent = True)
    
    if body is None:
        return jsonify({'msg': "Debe enviar info al body"}), 400
    if 'email' not in body:
        return jsonify({'msg': "El campo email es obligatorio"}), 400
    if 'password' not in body:
        return jsonify({'msg': "El campo password es obligatorio"}), 400
    # Fetch user from database
    doctor = Doctor.query.filter_by(email=body["email"]).first()
    #Check if user exists
    if doctor is None:
        return jsonify({"msg": "Bad username"}), 401
    #devuelve TRUE si la contraseña es correcta
    password_correct = bcrypt.check_password_hash(doctor.password, body['password'])
    if not password_correct:
        return jsonify({"msg":"Wrong password"}), 401
    # Generate token
    access_token = create_access_token(identity=doctor.email)
    print(doctor)
    return jsonify({'msg': 'Login succesfull...',
                    'token': access_token,
                    'doctor': doctor.serialize()})

#GET Doctors
@app.route('/doctors', methods=['GET'])
def get_doctors():
    doctors = Doctor.query.all()

    doctors_serialized = []
    for doctor in doctors:
        doctors_serialized.append(doctor.serialize())

    response_body = {
        "msg": "ok",
        "result": doctors_serialized
    }

    return jsonify(response_body), 200

#GET Doctor by id
@app.route('/doctor/<int:doctor_id>', methods=['GET'])
def get_doctor(doctor_id):
    doctor = Doctor.query.get(doctor_id)
    print(doctor.serialize())
    if doctor:
        doctor_data = { 
            "id": doctor.id,
            "name": doctor.name,
            "surname": doctor.surname,
            "email": doctor.email,
            "bio": doctor.bio,
            "speciality_id": doctor.speciality_id,
            # "review": doctor.review,
            "speciality": doctor.speciality,
            "is_active": doctor.is_active
        }
        return jsonify({"message": "Doctor founded", "user": doctor_data}), 200
    return jsonify({"message": "Doctor not found"}), 404

#PUT Doctor by id
@app.route('/doctor/<int:doctor_id>', methods=['PUT'])
def update_doctor(doctor_id):
    doctor = Doctor.query.get(doctor_id)
    if doctor:
        data = request.json
        doctor.name = data.get('name', doctor.name)
        doctor.surname = data.get('surname', doctor.surname)
        doctor.age = data.get('age', doctor.age)
        doctor.identification = data.get('identification', doctor.identification)
        doctor.medical_license = data.get('medical_license', doctor.medical_license)
        doctor.email = data.get('email', doctor.email)
        doctor.password = data.get('password', doctor.password)
        doctor.speciality = data.get('speciality', doctor.speciality)
        doctor.is_active = data.get('is_active', doctor.is_active)
        db.session.commit()
        return jsonify({"message": "User updated"}), 200
    return jsonify({"message": "User not found"}), 404

#DELETE Doctor by id
@app.route('/doctor/<int:doctor_id>', methods=['DELETE'])
def delete_doctor(doctor_id):
    doctor = Doctor.query.get(doctor_id)
    if doctor:
        db.session.delete(doctor)
        db.session.commit()
        return jsonify({"message": "Doctor deleted"}), 200
    return jsonify({"message": "Doctor not found"}), 404

#Doctor Availability
@app.route("/api/doctor_availability/<int:doctor_id>", methods=["GET"])
def get_doctor_availability(doctor_id):
    doctor = Doctor.query.get(doctor_id)
    if doctor is None:
        return jsonify({'error': "El doctor especificado no existe", 'doctor_id': doctor_id}), 404

    availability = [availability.serialize() for availability in doctor.availabilities]
    return jsonify({'availability': availability}), 200





#Register Speciality    
@app.route("/api/register/speciality", methods=["POST"])
def register_speciality():
    body = request.get_json(silent=True)
    
    if body is None or 'name' not in body:
        return jsonify({'msg': "Debes enviar el nombre de la especialidad en el cuerpo de la solicitud"}), 400
    
    new_speciality = Speciality()
    new_speciality.name = body['name']
    new_speciality.is_active = True
    db.session.add(new_speciality)
    db.session.commit()

    return jsonify({"message": "Speciality registered successfully", "speciality": new_speciality.serialize()}), 201

#GET Speciality
@app.route('/specialities', methods=['GET'])
def get_specialities():
    specialities = Speciality.query.all()

    specialities_serialized = []
    for speciality in specialities:
        specialities_serialized.append(speciality.serialize())

    response_body = {
        "msg": "ok",
        "result": specialities_serialized
    }

    return jsonify(response_body), 200

#GET Speciality id
@app.route('/speciality/<int:speciality_id>', methods=['GET'])
def get_speciality(speciality_id):
    speciality = Speciality.query.get(speciality_id)
    if speciality:
        speciality_data = {
            "id": speciality.id,
            "name": speciality.name,
            "is_active": speciality.is_active
            
        }
        return jsonify({"message": "Speciality founded", "speciality": speciality_data}), 200
    return jsonify({"message": "Speciality not found"}), 404

#PUT Speciality by id
@app.route('/speciality/<int:speciality_id>', methods=['PUT'])
def update_speciality(speciality_id):
    speciality = Speciality.query.get(speciality_id)
    if speciality:
        data = request.json
        speciality.name = data.get('name', speciality.name)
        speciality.is_active = data.get('is_active', speciality.is_active)
        db.session.commit()
        return jsonify({"message": "User updated"}), 200
    return jsonify({"message": "User not found"}), 404

#DELETE Speciality by id
@app.route('/speciality/<int:speciality_id>', methods=['DELETE'])
def delete_speciality(speciality_id):
    speciality = Speciality.query.get(speciality_id)
    if speciality:
        db.session.delete(speciality)
        db.session.commit()
        return jsonify({"message": "Speciality deleted"}), 200
    return jsonify({"message": "Speciality not found"}), 404


# @app.route("/meetings", methods=["POST"])
def create_meeting():
    # Get the current date
    current_date = datetime.now()
    isoformat = current_date + timedelta(weeks=2)
    data = {
        "isLocked": False,
        "roomNamePrefix": "",
        "roomNamePattern": "uuid",
        "roomMode": "normal",
        "endDate": isoformat.isoformat(),
        "fields": [
            "hostRoomUrl"
        ]
    }

    # Llama a la API de Whereby para crear una reunión
    api_token = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJodHRwczovL2FjY291bnRzLmFwcGVhci5pbiIsImF1ZCI6Imh0dHBzOi8vYXBpLmFwcGVhci5pbi92MSIsImV4cCI6OTAwNzE5OTI1NDc0MDk5MSwiaWF0IjoxNzEzNDU3NDAyLCJvcmdhbml6YXRpb25JZCI6MjI1NTEzLCJqdGkiOiI2NGUwNjlkNi1mYjBhLTRhYjMtYjkyOC1mYjFhY2NiOTM5OGYifQ.T5y4YmndKiciCuKqDsTZtyPCH1hqpDB4WsHbF--zNK8"
    headers = {
        "Authorization": f"Bearer {api_token}",
        "Content-Type": "application/json"
    }
    create_meeting_url = "https://api.whereby.dev/v1/meetings"
    
    response = requests.post(create_meeting_url, json=data, headers=headers)

    # if response.status_code != 201:
    #     return jsonify({"error": "Error al crear la reunión"}), response.status_code
    # print(response)

    # Obtiene la respuesta de la API de Whereby
    room_data = response.json()
    # print("despues de aqui room_data")
    # print(room_data)
    # Actualiza la respuesta con el enlace correcto
    # meeting = {
    #     "meetingId": room_data["meetingId"],
    #     "endDate": room_data["endDate"],
    #     "roomUrl": room_data["roomUrl"],
    #     "startDate": room_data["startDate"],
    #     "roomName": room_data["roomName"],
    #     "hostRoomUrl": f"{room_data['roomUrl']}/host",
    #     "viewerRoomUrl": f"{room_data['roomUrl']}/viewer"
    # }
    # # meetings.append(meeting)
    # print(meeting)
    return (room_data)



#Register Medical Appoinment    

@app.route("/api/register/medical_appointment", methods=["POST"])
@jwt_required()
def register_medical_appointment():
    body = request.get_json(silent=True)
    
    if body is None:
        return jsonify({'msg': "Debes enviar info al body"}), 400
    
    patient = get_jwt_identity()
    patient_info = Patient.query.filter_by(email=patient).first()

    if 'doctor_id' not in body or 'appointment_time' not in body or 'speciality' not in body:  
        return jsonify({'msg': "Los campos doctor_id, appointment_time y speciality son obligatorios"}), 400

    doctor_id = body.get('doctor_id')
    appointment_time_str = body.get('appointment_time')

    try:
        appointment_time = datetime.fromisoformat(appointment_time_str)
    except ValueError:
        return jsonify({'msg': "Formato de fecha y hora incorrecto"}), 400

    doctor = Doctor.query.get(doctor_id)
    if doctor is None:
        return jsonify({'msg': "El doctor especificado no existe"}), 404

    if not doctor.is_available(appointment_time):
        return jsonify({'msg': "El doctor no está disponible en la fecha y hora especificadas"}), 400

    existing_appointment = Medical_Appointment.query.filter_by(
        doctor_id=doctor_id,
        appointment_date=appointment_time
    ).first()

    if existing_appointment:
        return jsonify({'msg': "La cita ya está reservada"}), 400

    new_medical_appointment = Medical_Appointment(
        speciality_id=body['speciality'],
        patient_id=patient_info.id,
        doctor_id=doctor_id,
        appointment_date=appointment_time,
        
        is_active=True
    )
    
    db.session.add(new_medical_appointment)
    db.session.commit()

    # Genera los enlaces de videoconferencia para la cita médica
    meeting_room_data = create_meeting()
    meeting_data = {
        "endDate": appointment_time.isoformat(),
        "roomNamePrefix": meeting_room_data['roomUrl'],
        "HostroomNamePrefix": meeting_room_data['hostRoomUrl'],
        "meetingId": meeting_room_data['meetingId']
    }
    meeting_links = create_meeting_links(meeting_data)
    
    print(meeting_room_data) 
    
    # Envía correos electrónicos al paciente y al doctor
    send_emails(patient_info.email, patient_info.id, doctor.email, appointment_time, meeting_links)

    return jsonify({"message": "La cita médica se registró correctamente"}), 201

def create_meeting_links(data):
    # Simulación de la generación de enlaces de videoconferencia
    room_url = f"{data['roomNamePrefix']}"
    host_room_url = f"{data['HostroomNamePrefix']}"
    return room_url, host_room_url

def send_emails(patient_email, patient_id, doctor_email, appointment_time, meeting_links):
    room_url, host_room_url = meeting_links
    
    # Construye el mensaje de correo electrónico con los detalles de la cita y los enlaces de videoconferencia
    msg_patient = Message(subject="Detalles de tu cita médica", sender='mediconecta1@gmail.com', recipients=[patient_email])
    msg_patient.html = f"<h1>Detalles de tu cita médica:</h1><h3>Su cita medica se ha agendado satisfactoriamente para el:</h3><p>Fecha y hora: {appointment_time}</p><h3>Ingrese al link en la fecha y hora indicada para ser atendido:</h3><p>Enlace de la sala de espera: {room_url}</p>"
    mail.send(msg_patient)
    
    msg_doctor = Message(subject="Nueva cita médica agendada", sender='mediconecta1@gmail.com', recipients=[doctor_email])
    msg_doctor.html = f"<h1>Detalles de la cita médica con paciente {patient_id}:</h1><h3>Ingrese al link a la fecha y hora indicada:</h3><p>Fecha y hora: {appointment_time}</p><p>Enlace de la sala de host: {host_room_url}</p>"
    mail.send(msg_doctor)






#GET medical_appoinments
@app.route('/medical_appoinments', methods=['GET'])
def get_medical_appoinments():
    medical_appoinments = Medical_Appointment.query.all()

    medical_appoinments_serialized = []
    for medical_appoinment in medical_appoinments:
        medical_appoinments_serialized.append(medical_appoinment.serialize())

    response_body = {
        "msg": "ok",
        "result": medical_appoinments_serialized
    }

    return jsonify(response_body), 200

#GET medical_appoinment by id
@app.route('/medical_appoinment/<int:medical_appoinment_id>', methods=['GET'])
def get_medical_appoinment(medical_appoinment_id):
    medical_appoinment = Medical_Appointment.query.get(medical_appoinment_id)
    if medical_appoinment:
        medical_appoinment_data = {
            "id": medical_appoinment.id,
            "is_active": medical_appoinment.is_active
            
        }
        return jsonify({"message": "Medical Appoinment founded", "medical_appoinment": medical_appoinment_data}), 200
    return jsonify({"message": "Medical Appoinment not found"}), 404

#PUT medical_appoinment by id
@app.route('/medical_appoinment/<int:medical_appoinment_id>', methods=['PUT'])
def update_medical_appoinment(medical_appoinment_id):
    medical_appoinment = Medical_Appointment.query.get(medical_appoinment_id)
    if medical_appoinment:
        data = request.json
        medical_appoinment.id = data.get('id', medical_appoinment.id)
        medical_appoinment.is_active = data.get('is_active', medical_appoinment.is_active)
        db.session.commit()
        return jsonify({"message": "Medical Appoinment updated"}), 200
    return jsonify({"message": "Medical Appoinment not found"}), 404

#DELETE Medical_appoinment by id
@app.route('/medical_appoinment/<int:medical_appoinment_id>', methods=['DELETE'])
def delete_medical_appoinment(medical_appoinment_id):
    medical_appoinment = Medical_Appointment.query.get(medical_appoinment_id)
    if medical_appoinment:
        db.session.delete(medical_appoinment)
        db.session.commit()
        return jsonify({"message": "Medical Appoinment deleted"}), 200
    return jsonify({"message": "Medical Appoinment not found"}), 404

#Register Alergic    
@app.route("/api/register/alergic", methods=["POST"])

def register_alergic():
    body = request.get_json (silent = True)
    
    if body is None:
        return jsonify({'msg': "Debes enviar info al body"}), 400
    
    
    new_alergic = Alergic()
    new_alergic.name = body['name']
    new_alergic.is_active = True
    db.session.add(new_alergic)
    db.session.commit()

    return jsonify({"message": "Alergic registered successfully"}), 201

#GET Alergics
@app.route('/alergics', methods=['GET'])
def get_alergics():
    alergics = Alergic.query.all()

    alergics_serialized = []
    for alergic in alergics:
        alergics_serialized.append(alergic.serialize())

    response_body = {
        "msg": "ok",
        "result": alergics_serialized
    }

    return jsonify(response_body), 200

#GET Alergic by id
@app.route('/alergic/<int:alergic_id>', methods=['GET'])
def get_alergic(alergic_id):
    alergic = Alergic.query.get(alergic_id)
    if alergic:
        alergic_data = {
            "id": alergic.id,
            "name": alergic.name,
            "is_active": alergic.is_active
            
        }
        return jsonify({"message": "Alergic founded", "medical_appoinment": alergic_data}), 200
    return jsonify({"message": "Alergic not found"}), 404

#PUT Alergic by id
@app.route('/alergic/<int:alergic_id>', methods=['PUT'])
def update_alergic(alergic_id):
    alergic = Alergic.query.get(alergic_id)
    if alergic:
        data = request.json
        alergic.name = data.get('name', alergic.name)
        alergic.is_active = data.get('is_active', alergic.is_active)
        db.session.commit()
        return jsonify({"message": "Alergic updated"}), 200
    return jsonify({"message": "Alergic not found"}), 404

#DELETE Alergic by id
@app.route('/alergic/<int:alergic_id>', methods=['DELETE'])
def delete_alergic(alergic_id):
    alergic = Alergic.query.get(alergic_id)
    if alergic:
        db.session.delete(alergic)
        db.session.commit()
        return jsonify({"message": "Alergic deleted"}), 200
    return jsonify({"message": "Alergic not found"}), 404

#Register Medicated    
@app.route("/api/register/medicated", methods=["POST"])

def register_medicated():
    body = request.get_json (silent = True)
    
    if body is None:
        return jsonify({'msg': "Debes enviar info al body"}), 400
    
    
    new_medicated = Medicated()
    new_medicated.name = body['name']
    new_medicated.is_active = True
    db.session.add(new_medicated)
    db.session.commit()

    return jsonify({"message": "Medicated registered successfully"}), 201

#GET Medicated
@app.route('/medicateds', methods=['GET'])
def get_medicateds():
    medicateds = Medicated.query.all()

    medicateds_serialized = []
    for medicated in medicateds:
        medicateds_serialized.append(medicated.serialize())

    response_body = {
        "msg": "ok",
        "result": medicateds_serialized
    }

    return jsonify(response_body), 200

#GET Medicated by id
@app.route('/medicated/<int:medicated_id>', methods=['GET'])
def get_medicated(medicated_id):
    medicated = Medicated.query.get(medicated_id)
    if medicated:
        medicated_data = {
            "id": medicated.id,
            "name": medicated.name,
            "is_active": medicated.is_active
            
        }
        return jsonify({"message": "Alergic founded", "medical_appoinment": medicated_data}), 200
    return jsonify({"message": "Alergic not found"}), 404

#PUT Medicated by id
@app.route('/medicated/<int:medicated_id>', methods=['PUT'])
def update_medicated(medicated_id):
    medicated = Medicated.query.get(medicated_id)
    if medicated:
        data = request.json
        medicated.name = data.get('name', medicated.name)
        medicated.is_active = data.get('is_active', medicated.is_active)
        db.session.commit()
        return jsonify({"message": "Medicated updated"}), 200
    return jsonify({"message": "Medicated not found"}), 404

#DELETE Medicated by id
@app.route('/medicated/<int:medicated_id>', methods=['DELETE'])
def delete_medicated(medicated_id):
    medicated = Medicated.query.get(medicated_id)
    if medicated:
        db.session.delete(medicated)
        db.session.commit()
        return jsonify({"message": "Alergic deleted"}), 200
    return jsonify({"message": "Alergic not found"}), 404

#SEND EMAIL
# @app.route('/send_mail', methods=['GET'])
# def send_mail():
#     msg = Message(subject="Prueba mail desde test", sender='mediconecta1@gmail.com',
#                   recipients=['mediconecta1@gmail.com'])
#     msg.html = "<h1> Hola desde el correo</h1>"
#     mail.send(msg)
#     return jsonify ({"msg": "Mail enviado!!!"})



@app.route('/send_mail', methods=['POST'])
def send_mail():
    data = request.json
    
    if data is None:
        return jsonify({"msg": "Debes enviar la información del correo electrónico en el cuerpo de la solicitud"}), 400

    patient_email = data.get('patient_email')
    doctor_email = data.get('doctor_email')
    appointment_time = data.get('appointment_time')

    if not all([patient_email, doctor_email, appointment_time]):
        return jsonify({"msg": "Falta información requerida para enviar el correo electrónico"}), 400

    msg_patient = Message(subject="Detalles de tu cita médica", sender='mediconecta1@gmail.com', recipients=[patient_email])
    msg_patient.html = f"<h1>Detalles de tu cita médica</h1><p>Fecha y hora: {appointment_time}</p>"
    mail.send(msg_patient)
    
    msg_doctor = Message(subject="Detalles de la cita médica de un paciente", sender='mediconecta1@gmail.com', recipients=[doctor_email])
    msg_doctor.html = f"<h1>Detalles de la cita médica de un paciente</h1><p>Fecha y hora: {appointment_time}</p>"
    mail.send(msg_doctor)

    return jsonify({"msg": "Correos electrónicos enviados correctamente"}), 200



# Meetings





@app.route("/meetings", methods=["GET"])
def get_meetings():
    return jsonify(meetings)

@app.route("/meetings/<meetingId>", methods=["GET"])
def get_meeting(meetingId):
    for meeting in meetings:
        if meeting["meetingId"] == meetingId:
            return jsonify(meeting)
    return jsonify({"message": "Meeting not found"}), 404

@app.route("/meetings/<meetingId>", methods=["DELETE"])
def delete_meeting(meetingId):
    global meetings
    meetings = [meeting for meeting in meetings if meeting["meetingId"] != meetingId]
    return jsonify({"message": "Meeting deleted successfully"})

# Summaries
summaries = []

@app.route("/summaries", methods=["GET"])
def get_summaries():
    return jsonify(summaries)

@app.route("/summaries", methods=["POST"])
def create_summary():
    data = request.json
    summary = {
        "summaryId": str(len(summaries) + 1),
        "transcriptionId": data["transcriptionId"],
        "summary": f"This is a summary for transcription {data['transcriptionId']}",
        "template": data["template"]
    }
    summaries.append(summary)
    return jsonify(summary)

@app.route("/summaries/<summaryId>", methods=["GET"])
def get_summary(summaryId):
    for summary in summaries:
        if summary["summaryId"] == summaryId:
            return jsonify(summary)
    return jsonify({"message": "Summary not found"}), 404

@app.route("/summaries/<summaryId>", methods=["DELETE"])
def delete_summary(summaryId):
    global summaries
    summaries = [summary for summary in summaries if summary["summaryId"] != summaryId]
    return jsonify({"message": "Summary deleted successfully"})

# Favorite Routes

# @app.route('/user/favorites', methods=['GET'])
# def favorites():
#     body = request.get_json(silent=True)
#     if body is None:
#         return jsonify({'msg': "debes enviar informacion en el body"}), 400
#     if 'patient_id' not in body:
#         return jsonify({'msg': 'El campo patient_id es obligatorio'}), 400
#     patient = Patient.query.get(body['patient_id'])
#     if patient is None:
#         return jsonify({'msg': "El paciente con el id {} no existe".format(body['patient_id'])}), 404
#     """favorite_speciality = db.session.query(FavoriteSpeciality, Speciality).join(Speciality).filter(FavoriteSpeciality.patient_id==body['patient_id']).all()
#     favorite_speciality_serialized = []
#     for favorite_item, speciality_item in favorite_speciality:
#         favorite_speciality_serialized.append({"favorite_speciality_id": favorite_item.id, "speciality": speciality_item.serialize()})
#         return jsonify({"msg": "ok", "results": favorite_speciality_serialized})
#     favorite_doctor= db.session.query(FavoriteDoctor, Doctor).join(Doctor).filter(FavoriteDoctor.patient_id==body['patient_id']).all()
#     favorite_doctor_serialized = []
#     for favorite_item, doctor_item in favorite_doctor:
#         favorite_doctor_serialized.append({"favorite_doctor_id": favorite_item.id, "doctor": doctor_item.serialize()})
#         return jsonify({"msg": "ok", "results": favorite_doctor_serialized})"""
#     favorite_medical_appointment = db.session.query(Favorite_Medical_Appointment, Medical_Appointment).join(Medical_Appointment).filter(Favorite_Medical_Appointment.patient_id==body['patient_id']).all()
#     favorite_medical_appointment_serialized = []
#     for favorite_item, medical_appointment_item in favorite_medical_appointment:
#         favorite_medical_appointment_serialized.append({"favorite_medical_appointment_id": favorite_item.id, "medical_appointment": medical_appointment_item.serialize()})
#         return jsonify({"msg": "ok", "results": favorite_medical_appointment_serialized})
#     print(patient)
#     return jsonify({'msg': 'ok'})

# Protect a route with jwt_required, which will kick out request
# without a valid JWT present.
'''@app.route("/api/protected", methods=["GET"])
@jwt_required()
def protected():
    # Access the identity of the current patient with get_jwt_identity
    current_patient = get_jwt_identity()
    return jsonify(logged_in_as=current_patient), 200'''

@app.route("/api/protected", methods=["GET"])
@jwt_required()
def protected():
    # Access the identity of the current user with get_jwt_identity
    current_user = get_jwt_identity()
    return jsonify(logged_in_as=current_user), 200

# this only runs if `$ python src/main.py` is executed
if __name__ == '__main__':
    PORT = int(os.environ.get('PORT', 3001))
    app.run(host='0.0.0.0', port=PORT, debug=True)