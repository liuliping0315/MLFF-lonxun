#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from statistics import mode
from turtle import Turtle
import torch
import os,sys
import random
import time
import numpy as np
import torch.autograd as autograd
import matplotlib.pyplot as plt
import torch.nn as nn


#print(os.path.abspath(sys.path[0]))
import torch.nn.functional as F
from torch.nn.modules import loss
import torch.optim as optim
from torch.nn.parameter import Parameter
from torch.utils.data import Dataset, DataLoader
from loss.AutomaticWeightedLoss import AutomaticWeightedLoss
from model.MLFF_v1 import MLFF
from model.MLFF import MLFFNet

from optimizer.kalmanfilter import GKalmanFilter, LKalmanFilter, SKalmanFilter

from model.dp import DP
import torch.utils.data as Data
from torch.autograd import Variable
import math
sys.path.append(os.getcwd())
#import parameters as pm 
codepath=os.path.abspath(sys.path[0])

sys.path.append(codepath+'/pre_data')
sys.path.append(codepath+'/..')
import use_para as pm
import parse_input
parse_input.parse_input()

from data_loader_2type import MovementDataset, get_torch_data
from scalers import DataScalers
from utils import get_weight_grad

# module to use the sparse dfeat
from dfeat_sparse import dfeat_raw 

from torch.utils.tensorboard import SummaryWriter
# from tensorboardX import SummaryWriter
import time
import getopt
import getpass

from sklearn.preprocessing import MinMaxScaler
from joblib import dump, load
from sklearn.feature_selection import VarianceThreshold
import pickle
# logging and our extension
import logging
logging_level_DUMP = 5
logging_level_SUMMARY = 15

# parse optional parameters
opt_force_cpu = False
opt_magic = False
opt_follow_mode = False
opt_recover_mode = False
opt_net_cfg = 'default'
# opt_act = 'tanh'
opt_act = 'sigmoid'
opt_optimizer = 'ADAM'
opt_momentum = float(0)
opt_regular_wd = float(0)
opt_scheduler = 'NONE'
opt_epochs = pm.n_epoch
opt_lr = float(0.001)
opt_gamma = float(0.99)
opt_step = 100
opt_batch_size = pm.batch_size
opt_dtype = pm.training_dtype
opt_rseed = 2021
# session and related options
opt_session_name = ''
opt_session_dir = ''
opt_logging_file = ''
opt_tensorboard_dir = ''
opt_model_dir = ''
opt_model_file = ''
opt_run_id = ''
# end session related
opt_log_level = logging.INFO
opt_file_log_level = logging.DEBUG
opt_journal_cycle = 1
# wandb related
opt_wandb = False
opt_wandb_entity = 'moleculenn'
opt_wandb_project = 'MLFF_torch'
# end wandb related
opt_init_b = False
opt_save_model = False

# scheduler specific options
opt_LR_milestones = None
opt_LR_patience = 0
opt_LR_cooldown = 0
opt_LR_total_steps = None
opt_LR_max_lr = 1.
opt_LR_min_lr = 0.
opt_LR_T_max = None
opt_autograd = True
opt_dp = False

# layerwised Kalman Filter options
opt_nselect = 24
opt_groupsize= 6
opt_blocksize = 5120
opt_fprefactor = 2

opts,args = getopt.getopt(sys.argv[1:],
    '-h-c-m-f-R-n:-a:-z:-v:-w:-u:-e:-l:-g:-t:-b:-d:-r:-s:-o:-i:-j:',
    ['help','cpu','magic','follow','recover','net_cfg=','act=','optimizer=','momentum',
     'weight_decay=','scheduler=','epochs=','lr=','gamma=','step=',
     'batch_size=','dtype=','rseed=','session=','log_level=',
     'file_log_level=','j_cycle=','init_b','save_model',
     'milestones=','patience=','cooldown=','eps=','total_steps=',
     'max_lr=','min_lr=','T_max=',
     'wandb','wandb_entity=','wandb_project=',
     'auto_grad=', 'dmirror=', 'dp=', 'nselect=', 'groupsize=', 'blocksize=', 'fprefactor='])

for opt_name,opt_value in opts:
    if opt_name in ('-h','--help'):
        print("")
        print("Generic parameters:")
        print("     -h, --help                  :  print help info")
        print("     -c, --cpu                   :  force training run on cpu")
        print("     -m, --magic                 :  a magic flag for your testing code")
        print("     -f, --follow                :  follow a previous trained model file")
        print("     -R, --recover               :  breakpoint training")
        print("     -n cfg, --net_cfg=cfg       :  if -f/--follow is not set, specify network cfg in parameters.py")
        print("                                    eg: -n MLFF_dmirror_cfg1")
        print("                                    if -f/--follow is set, specify the model image file name")
        print("                                    eg: '-n best1' will load model image file best1.pt from session dir")
        print("     -a act, --act=act           :  specify activation_type of MLFF_dmirror")
        print("                                    current supported: [sigmoid, softplus]")
        print("     -z name, --optimizer=name   :  specify optimizer")
        print("                                    available : SGD ASGD RPROP RMSPROP ADAG")
        print("                                                ADAD ADAM ADAMW ADAMAX LBFGS")
        print("     -v val, --momentum=val      :  specify momentum parameter for optimizer")
        print("     -w val, --weight_decay=val  :  specify weight decay regularization value")
        print("     -u name, --scheduler=name   :  specify learning rate scheduler")
        print("                                    available  : LAMBDA STEP MSTEP EXP COS PLAT OC LR_INC LR_DEC")
        print("                                    LAMBDA     : lambda scheduler")
        print("                                    STEP/MSTEP : Step/MultiStep scheduler")
        print("                                    EXP/COS    : Exponential/CosineAnnealing") 
        print("                                    PLAT/OC/LR : ReduceLROnPlateau/OneCycle")
        print("                                    LR_INC     : linearly increase to max_lr")
        print("                                    LR_DEC     : linearly decrease to min_lr")
        print("     -e epochs, --epochs=epochs  :  specify training epochs")
        print("     -l lr, --lr=lr              :  specify initial training lr")
        print("     -g gamma, --gamma=gamma     :  specify gamma of StepLR scheduler")
        print("     -t step, --step=step        :  specify step_size of StepLR scheduler")
        print("     -b size, --batch_size=size  :  specify batch size")
        print("     -d dtype, --dtype=dtype     :  specify default dtype: [float64, float32]")
        print("     -r seed, --rseed=seed       :  specify random seed used in training")
        print("     -s name, --session=name     :  specify the session name, log files, tensorboards and models")
        print("                                    will be saved to subdirectory named by this session name")
        print("     -o level, --log_level=level :  specify logging level of console")
        print("                                    available: DUMP < DEBUG < SUMMARY < [INFO] < WARNING < ERROR")
        print("                                    logging msg with level >= logging_level will be displayed")
        print("     -i L, --file_log_level=L    :  specify logging level of log file")
        print("                                    available: DUMP < [DEBUG] < SUMMARY < INFO < WARNING < ERROR")
        print("                                    logging msg with level >= logging_level will be recoreded")
        print("     -j val, --j_cycle=val       :  specify journal cycle for tensorboard and data dump")
        print("                                    0: disable journaling")
        print("                                    1: record on every epoch [default]")
        print("                                    n: record on every n epochs")
        print("")
        print("scheduler specific parameters:")
        print("     --milestones=int_list       :  milestones for MultiStep scheduler")
        print("     --patience=int_val          :  patience for ReduceLROnPlateau")
        print("     --cooldown=int_val          :  cooldown for ReduceLROnPlateau")
        print("     --total_steps=int_val       :  total_steps for OneCycle scheduler")
        print("     --max_lr=float_val          :  max learning rate for OneCycle scheduler")
        print("     --min_lr=float_val          :  min learning rate for CosineAnnealing/ReduceLROnPlateau")
        print("     --T_max=int_val             :  T_max for CosineAnnealing scheduler")
        print("")
        print("     --dmirror                   :  calculate dE/dx layer by layer explicitly")
        print("     --auto_grad                 :  calculate dE/dx by autograd func")
        print("                                    using --dmirror or --auto_grad")
        print("                                    default: --auto_grad")
        print("")
        print("     --dp                    :  use dp method(emdedding net + fitting net)")
        print("                                    using --dp=True enable dp method")
        print("                                    adding -n DeepMD_cfg (see cu/parameters.py)")
        print("                                    defalt: --dp=False (see line 90)")
        print("")
        print("wandb parameters:")
        print("     --wandb                     :  ebable wandb, sync tensorboard data to wandb")
        print("     --wandb_entity=yr_account   :  your wandb entity or account (default is: moleculenn")
        print("     --wandb_project=yr_project  :  your wandb project name (default is: MLFF_torch)")
        print("")
        print("Kalman Filter parameters:")
        print("     --nselect                   :  sample force number(default:24)")
        print("     --groupsize                 :  the number of atoms for one iteration by force(default:6)")
        print("     --blocksize                 :  max weights number for KF update(default:5120)")
        print("     --fprefactor                :  LKF force prefactor(default:2)")
        print("")
        exit()
    elif opt_name in ('-c','--cpu'):
        opt_force_cpu = True
    elif opt_name in ('-m','--magic'):
        opt_magic = True
    elif opt_name in ('-R','--recover'):
        opt_recover_mode = True
        print(opt_recover_mode)
        # opt_follow_epoch = int(opt_value)
    elif opt_name in ('-f','--follow'):
        opt_follow_mode = True
        # opt_follow_epoch = int(opt_value)
    elif opt_name in ('-n','--net_cfg'):
        opt_net_cfg = opt_value
    elif opt_name in ('-a','--act'):
        opt_act = opt_value
    elif opt_name in ('-z','--optimizer'):
        opt_optimizer = opt_value
    elif opt_name in ('-v','--momentum'):
        opt_momentum = float(opt_value)
    elif opt_name in ('-w','--weight_decay'):
        opt_regular_wd = float(opt_value)
    elif opt_name in ('-u','--scheduler'):
        opt_scheduler = opt_value
    elif opt_name in ('-e','--epochs'):
        opt_epochs = int(opt_value)
    elif opt_name in ('-l','--lr'):
        opt_lr = float(opt_value)
    elif opt_name in ('-g','--gamma'):
        opt_gamma = float(opt_value)
    elif opt_name in ('-t','--step'):
        opt_step = int(opt_value)
    elif opt_name in ('-b','--batch_size'):
        opt_batch_size = int(opt_value)
    elif opt_name in ('-d','--dtype'):
        opt_dtype = opt_value
    elif opt_name in ('-r','--rseed'):
        opt_rseed = int(opt_value)
    elif opt_name in ('-s','--session'):
        opt_session_name = opt_value
        opt_session_dir = './'+opt_session_name+'/'
        opt_logging_file = opt_session_dir+'train.log'
        opt_model_dir = opt_session_dir+'model/'
        tensorboard_base_dir = opt_session_dir+'tensorboard/'
        if not os.path.exists(opt_session_dir):
            os.makedirs(opt_session_dir) 
        if not os.path.exists(opt_model_dir):
            os.makedirs(opt_model_dir)
        for i in range(1000):
            opt_run_id = 'run'+str(i)
            opt_tensorboard_dir = tensorboard_base_dir+opt_run_id
            if (not os.path.exists(opt_tensorboard_dir)):
                os.makedirs(opt_tensorboard_dir)
                break
        else:
            opt_tensorboard_dir = ''
            raise RuntimeError("reaches 1000 run dirs in %s, clean it" %opt_tensorboard_dir)
    elif opt_name in ('-o','--log_level'):
        if (opt_value == 'DUMP'):
            opt_log_level = logging_level_DUMP
        elif (opt_value == 'SUMMARY'):
            opt_log_level = logging_level_SUMMARY
        else:
            opt_log_level = 'logging.'+opt_value
            opt_log_level = eval(opt_log_level)
    elif opt_name in ('-i','--file_log_level'):
        if (opt_value == 'DUMP'):
            opt_file_log_level = logging_level_DUMP
        elif (opt_value == 'SUMMARY'):
            opt_file_log_level = logging_level_SUMMARY
        else:
            opt_file_log_level = 'logging.'+opt_value
            opt_file_log_level = eval(opt_file_log_level)
    elif opt_name in ('-j','--j_cycle'):
        opt_journal_cycle = int(opt_value)
    elif opt_name in ('--milestones'):
        opt_LR_milestones = list(map(int, opt_value.split(',')))
    elif opt_name in ('--patience'):
        opt_LR_patience = int(opt_value)
    elif opt_name in ('--cooldown'):
        opt_LR_cooldown = int(opt_value)
    elif opt_name in ('--total_steps'):
        opt_LR_total_steps = int(opt_value)
    elif opt_name in ('--max_lr'):
        opt_LR_max_lr = float(opt_value)
    elif opt_name in ('--min_lr'):
        opt_LR_min_lr = float(opt_value)
    elif opt_name in ('--T_max'):
        opt_LR_T_max = int(opt_value)
    elif opt_name in ('--wandb'):
        opt_wandb = True
        import wandb
    elif opt_name in ('--wandb_entity'):
        opt_wandb_entity = opt_value
    elif opt_name in ('--wandb_project'):
        opt_wandb_project = opt_value
    elif opt_name in ('--init_b'):
        opt_init_b = True
    elif opt_name in ('--save_model'):
        opt_save_model = True
    elif opt_name in ('--dmirror'):
        opt_autograd = False
    elif opt_name in ('--auto_grad'):
        opt_autograd = True
    elif opt_name in ('--dp='):
        opt_dp = eval(opt_value)
    elif opt_name in ('--nselect='):
        opt_nselect = eval(opt_value)
    elif opt_name in ('--groupsize='):
        opt_groupsize = eval(opt_value)
    elif opt_name in ('--blocksize='):
        opt_blocksize = eval(opt_value)
    elif opt_name in ('--fprefactor='):
        opt_fprefactor = eval(opt_value)

# setup logging module
logging.addLevelName(logging_level_DUMP, 'DUMP')
logging.addLevelName(logging_level_SUMMARY, 'SUMMARY')
logger = logging.getLogger('train')
logger.setLevel(logging_level_DUMP)

formatter = logging.Formatter("\33[0m\33[34;49m[%(name)s]\33[0m.\33[33;49m[%(levelname)s]\33[0m: %(message)s")
handler1 = logging.StreamHandler()
handler1.setLevel(opt_log_level)
handler1.setFormatter(formatter)
logger.addHandler(handler1)

if (opt_logging_file != ''):
    formatter = logging.Formatter("\33[0m\33[32;49m[%(asctime)s]\33[0m.\33[34;49m[%(name)s]\33[0m.\33[33;49m[%(levelname)s]\33[0m: %(message)s")
    handler2 = logging.FileHandler(filename = opt_logging_file)
    handler2.setLevel(opt_file_log_level)
    handler2.setFormatter(formatter)
    logger.addHandler(handler2)

def dump(msg, *args, **kwargs):
    logger.log(logging_level_DUMP, msg, *args, **kwargs)
def debug(msg, *args, **kwargs):
    logger.debug(msg, *args, **kwargs)
def summary(msg, *args, **kwargs):
    logger.log(logging_level_SUMMARY, msg, *args, **kwargs)
def info(msg, *args, **kwargs):
    logger.info(msg, *args, **kwargs)
def warning(msg, *args, **kwargs):
    logger.warning(msg, *args, **kwargs)
def error(msg, *args, **kwargs):
    logger.error(msg, *args, **kwargs, exc_info=True)

# show start logging banner to logging file
#
summary("")
summary("#########################################################################################")
summary("#            ___          __                         __      __  ___       __  ___      #")
summary("#      |\ | |__  |  |    |__) |  | |\ | |\ | | |\ | / _`    /__`  |   /\  |__)  |       #")
summary("#      | \| |___ |/\|    |  \ \__/ | \| | \| | | \| \__>    .__/  |  /~~\ |  \  |       #")
summary("#                                                                                       #")
summary("#########################################################################################")
summary("")
summary(' '.join(sys.argv))
summary("")

global_prefac_Etot = pm.kalman_prefac_Etot
global_prefac_Ei = pm.kalman_prefac_Ei
global_prefac_F  = pm.kalman_prefac_Force
decay_rate = 0.975

if pm.kfnn_trainEtot:
    print ("Etot prefactor:", global_prefac_Etot)

if pm.kfnn_trainEi:
    print ("Ei prefactor:", global_prefac_Ei)

if pm.kfnn_trainForce:
    print ("Force prefactor", global_prefac_F)

if (opt_dtype == 'float64'):
    info("Training: set default dtype to float64")
    torch.set_default_dtype(torch.float64)
elif (opt_dtype == 'float32'):
    info("Training: set default dtype to float32")
    torch.set_default_dtype(torch.float32)
else:
    error("Training: unsupported dtype: %s" %opt_dtype)
    raise RuntimeError("Training: unsupported dtype: %s" %opt_dtype)

# set training device

if (opt_force_cpu == True):
    device = torch.device('cpu')
else:
    device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
info("Training: device = %s" %device)

# set random seed
torch.manual_seed(opt_rseed)
torch.cuda.manual_seed(opt_rseed)
info("Training: rseed = %s" %opt_rseed)

# set print precision
torch.set_printoptions(precision = 16)

# set tensorboard
if (opt_tensorboard_dir != ''):
    if (opt_wandb is True):
        wandb.tensorboard.patch(root_logdir=opt_tensorboard_dir)
        wandb_run = wandb.init(entity=opt_wandb_entity, project=opt_wandb_project, reinit=True)
        wandb_run.name = getpass.getuser()+'-'+opt_session_name+'-'+opt_run_id
        wandb_run.save()
    writer = SummaryWriter(opt_tensorboard_dir)
else:
    writer = None


def get_loss_func(start_lr, real_lr, has_fi, lossFi, has_etot, loss_Etot, has_egroup, loss_Egroup, has_ei, loss_Ei, natoms_sum):
    start_pref_egroup = 0.02
    limit_pref_egroup = 1.0
    start_pref_F = 1000  #1000
    limit_pref_F = 1.0
    start_pref_etot = 0.02   
    limit_pref_etot = 1.0
    start_pref_ei = 0.02
    limit_pref_ei = 1.0
    pref_fi = has_fi * (limit_pref_F + (start_pref_F - limit_pref_F) * real_lr / start_lr)
    pref_etot = has_etot * (limit_pref_etot + (start_pref_etot - limit_pref_etot) * real_lr / start_lr)
    pref_egroup = has_egroup * (limit_pref_egroup + (start_pref_egroup - limit_pref_egroup) * real_lr / start_lr)
    pref_ei = has_ei * (limit_pref_ei + (start_pref_ei - limit_pref_ei) * real_lr / start_lr)
    l2_loss = 0
    if has_fi==1:
        l2_loss += pref_fi * lossFi      # * 108
    if has_etot==1:
        l2_loss += 1./natoms_sum * pref_etot * loss_Etot  # 1/108 = 0.009259259259, 1/64=0.015625
    if has_egroup==1:
        l2_loss += pref_egroup * loss_Egroup
    if has_ei==1:
        l2_loss += pref_ei * loss_Ei
    
    return l2_loss, pref_fi, pref_etot


# 第iter次迭代时进行计算并更新学习率
def adjust_lr(iter, start_lr=opt_lr, stop_lr=3.51e-8):
    stop_step = 1000000
    decay_step=5000
    decay_rate = np.exp(np.log(stop_lr/start_lr) / (stop_step/decay_step)) #0.9500064099092085
    real_lr = start_lr * np.power(decay_rate, (iter//decay_step))
    return real_lr
	

def train(sample_batches, model, optimizer, criterion, last_epoch, real_lr):
    if (opt_dtype == 'float64'):
        Ei_label = Variable(sample_batches['output_energy'][:,:,:].double().to(device))
        Force_label = Variable(sample_batches['output_force'][:,:,:].double().to(device))   #[40,108,3]
        Egroup_label = Variable(sample_batches['input_egroup'].double().to(device))
        input_data = Variable(sample_batches['input_feat'].double().to(device), requires_grad=True)
        dfeat = Variable(sample_batches['input_dfeat'].double().to(device))  #[40,108,100,42,3]
        egroup_weight = Variable(sample_batches['input_egroup_weight'].double().to(device))
        divider = Variable(sample_batches['input_divider'].double().to(device))
        # Ep_label = Variable(sample_batches['output_ep'][:,:,:].double().to(device))
        if pm.dR_neigh:
            dR = Variable(sample_batches['input_dR'].double().to(device), requires_grad=True)
            dR_neigh_list = Variable(sample_batches['input_dR_neigh_list'].to(device))
            Ri = Variable(sample_batches['input_Ri'].double().to(device), requires_grad=True)
            Ri_d = Variable(sample_batches['input_Ri_d'].to(device))

    elif (opt_dtype == 'float32'):
        Ei_label = Variable(sample_batches['output_energy'][:,:,:].float().to(device))
        Force_label = Variable(sample_batches['output_force'][:,:,:].float().to(device))   #[40,108,3]
        Egroup_label = Variable(sample_batches['input_egroup'].float().to(device))
        input_data = Variable(sample_batches['input_feat'].float().to(device), requires_grad=True)
        dfeat = Variable(sample_batches['input_dfeat'].float().to(device))  #[40,108,100,42,3]
        egroup_weight = Variable(sample_batches['input_egroup_weight'].float().to(device))
        divider = Variable(sample_batches['input_divider'].float().to(device))
        # Ep_label = Variable(sample_batches['output_ep'][:,:,:].float().to(device))
        if pm.dR_neigh:
            dR = Variable(sample_batches['input_dR'].float().to(device), requires_grad=True)
            dR_neigh_list = Variable(sample_batches['input_dR_neigh_list'].to(device))
            Ri = Variable(sample_batches['input_Ri'].double().to(device), requires_grad=True)
            Ri_d = Variable(sample_batches['input_Ri_d'].to(device))
    else:
        error("train(): unsupported opt_dtype %s" %opt_dtype)
        raise RuntimeError("train(): unsupported opt_dtype %s" %opt_dtype)


    atom_number = Ei_label.shape[1]
    Etot_label = torch.sum(Ei_label, dim=1)
    neighbor = Variable(sample_batches['input_nblist'].int().to(device))  # [40,108,100]
    ind_img = Variable(sample_batches['ind_image'].int().to(device))
    natoms_img = Variable(sample_batches['natoms_img'].int().to(device))


    if opt_dp:
        Etot_predict, Ei_predict, Force_predict = model(Ri, Ri_d, dR_neigh_list, natoms_img, egroup_weight, divider)
    else:
        Etot_predict, Ei_predict, Force_predict, Egroup_predict = model(input_data, dfeat, neighbor, natoms_img, egroup_weight, divider)
    
    optimizer.zero_grad()

    # Egroup_predict = model.get_egroup(egroup_weight, divider)   #[40,108,1]

    # Etot_deviation = Etot_predict - Etot_label     # [40,1]

    loss_Etot = torch.zeros([1,1],device = device)
    loss_Ei = torch.zeros([1,1],device = device)
    loss_F = torch.zeros([1,1],device = device)
    loss_Egroup = 0

    # update loss with repsect to the data used
    if pm.kfnn_trainEi:
        loss_Ei = criterion(Ei_predict, Ei_label)
    if pm.kfnn_trainEtot:
        loss_Etot = criterion(Etot_predict, Etot_label)
    if pm.kfnn_trainForce:
        loss_F = criterion(Force_predict, Force_label)

    """
    loss_F = criterion(Force_predict, Force_label)
    loss_Etot = criterion(Etot_predict, Etot_label)
    loss_Ei = criterion(Ei_predict, Ei_label)
    
    #loss_Egroup = criterion(Egroup_predict, Egroup_label)
    #loss_Ei = 0
    """ 
    start_lr = opt_lr
    w_f = 1 if pm.kfnn_trainForce == True else 0
    w_e = 1 if pm.kfnn_trainEtot == True else 0
    w_ei = 1 if pm.kfnn_trainEi == True else 0
    w_eg = 0 

    loss, pref_f, pref_e = get_loss_func(start_lr, real_lr, w_f, loss_F, w_e, loss_Etot, w_eg, loss_Egroup, w_ei, loss_Ei, natoms_img[0, 0].item())

    # using a total loss to update weights 
    loss.backward()

    # 打印权重
    # param = {}
    # for name, parameter in model.named_parameters():
    #     param[name] = parameter.grad.cpu().detach().numpy()
    #     print(param[name])
    #     break;
    # import ipdb; ipdb.set_trace()

    optimizer.step()

    """
    info("loss = %.16f (loss_etot = %.16f, loss_force = %.16f, RMSE_etot = %.16f, RMSE_force = %.16f)"\
     %(loss, loss_Etot, loss_F, loss_Etot ** 0.5, loss_F ** 0.5))
    """
    
    return loss, loss_Etot, loss_Ei, loss_F

def train_kalman(sample_batches, model, kalman, criterion, last_epoch, real_lr):
    if (opt_dtype == 'float64'):
        Ei_label = Variable(sample_batches['output_energy'][:,:,:].double().to(device))
        Force_label = Variable(sample_batches['output_force'][:,:,:].double().to(device))   #[40,108,3]
        Egroup_label = Variable(sample_batches['input_egroup'].double().to(device))
        input_data = Variable(sample_batches['input_feat'].double().to(device), requires_grad=True)
        dfeat = Variable(sample_batches['input_dfeat'].double().to(device))  #[40,108,100,42,3]
        egroup_weight = Variable(sample_batches['input_egroup_weight'].double().to(device))
        divider = Variable(sample_batches['input_divider'].double().to(device))
        # Ep_label = Variable(sample_batches['output_ep'][:,:,:].double().to(device))
        if pm.dR_neigh:
            dR = Variable(sample_batches['input_dR'].double().to(device), requires_grad=True)
            dR_neigh_list = Variable(sample_batches['input_dR_neigh_list'].to(device))
            Ri = Variable(sample_batches['input_Ri'].double().to(device), requires_grad=True)
            Ri_d = Variable(sample_batches['input_Ri_d'].to(device))

    elif (opt_dtype == 'float32'):
        Ei_label = Variable(sample_batches['output_energy'][:,:,:].float().to(device))
        Force_label = Variable(sample_batches['output_force'][:,:,:].float().to(device))   #[40,108,3]
        Egroup_label = Variable(sample_batches['input_egroup'].float().to(device))
        input_data = Variable(sample_batches['input_feat'].float().to(device), requires_grad=True)
        dfeat = Variable(sample_batches['input_dfeat'].float().to(device))  #[40,108,100,42,3]
        egroup_weight = Variable(sample_batches['input_egroup_weight'].float().to(device))
        divider = Variable(sample_batches['input_divider'].float().to(device))
        # Ep_label = Variable(sample_batches['output_ep'][:,:,:].float().to(device))
        if pm.dR_neigh:
            dR = Variable(sample_batches['input_dR'].float().to(device), requires_grad=True)
            dR_neigh_list = Variable(sample_batches['input_dR_neigh_list'].to(device))
            Ri = Variable(sample_batches['input_Ri'].double().to(device), requires_grad=True)
            Ri_d = Variable(sample_batches['input_Ri_d'].to(device))
    else:
        error("train(): unsupported opt_dtype %s" %opt_dtype)
        raise RuntimeError("train(): unsupported opt_dtype %s" %opt_dtype)

    atom_number = Ei_label.shape[1]
    Etot_label = torch.sum(Ei_label, dim=1)
    neighbor = Variable(sample_batches['input_nblist'].int().to(device))  # [40,108,100]
    ind_img = Variable(sample_batches['ind_image'].int().to(device))
    natoms_img = Variable(sample_batches['natoms_img'].int().to(device))

    if opt_dp:
        # kalman_inputs = [dR, dfeat, dR_neigh_list, natoms_img, egroup_weight, divider]
        kalman_inputs = [Ri, Ri_d, dR_neigh_list, natoms_img, egroup_weight, divider]
    else:
        kalman_inputs = [input_data, dfeat, neighbor, natoms_img, egroup_weight, divider]

	# choosing what data are used for W update. Defualt are Etot and Force
    if pm.kfnn_trainEtot:
        kalman.update_energy(kalman_inputs, Etot_label, update_prefactor = global_prefac_Etot)

    if pm.kfnn_trainEi:
        kalman.update_ei(kalman_inputs,Ei_label, update_prefactor = global_prefac_Ei)

    if pm.kfnn_trainForce:
        kalman.update_force(kalman_inputs, Force_label, update_prefactor = global_prefac_F)

    if pm.kfnn_trainEgroup:
        kalman.update_egroup(kalman_inputs, Egroup_label)


    #kalman.update_ei_and_force(kalman_inputs,Ei_label,Force_label,update_prefactor = 0.1)

    
    if opt_dp:

        Etot_predict, Ei_predict, Force_predict = model(Ri, Ri_d, dR_neigh_list, natoms_img, egroup_weight, divider)
    else:
        Etot_predict, Ei_predict, Force_predict = model(input_data, dfeat, neighbor, natoms_img, egroup_weight, divider)

    Egroup_predict = torch.zeros_like(Ei_predict)

    if pm.kfnn_trainEgroup:
        Egroup_predict = model.get_egroup(Ei_predict,egroup_weight,divider) 

    # dtype same as torch.default
    loss_Etot = torch.zeros([1,1],device = device)
    loss_Ei = torch.zeros([1,1], device = device)
    loss_F = torch.zeros([1,1],device = device)
    loss_egroup = torch.zeros([1,1],device = device)

    """
        update loss with repsect to the data used.  
        At least 2 flags should be true. 
    """

    if pm.kfnn_trainEi:
        loss_Ei = criterion(Ei_predict, Ei_label)
    
    if pm.kfnn_trainEtot:
        loss_Etot = criterion(Etot_predict, Etot_label)

    if pm.kfnn_trainForce:
        loss_F = criterion(Force_predict, Force_label)

    if pm.kfnn_trainEgroup:
        loss_egroup = criterion(Egroup_label,Egroup_predict)

    loss = loss_F + loss_Etot + loss_Ei + loss_egroup 
    
    """
    if pm.kfnn_trainForce and pm.kfnn_trainEi:
        info("RMSE_Ei = %.12f, RMSE_Force = %.12f" %(loss_Ei ** 0.5, loss_F ** 0.5))
    elif pm.kfnn_trainEtot and pm.kfnn_trainForce:  
        info("RMSE_Etot = %.12f, RMSE_Force = %.12f" %(loss_Etot ** 0.5, loss_F ** 0.5))
    """
    
    info("RMSE_Etot = %.12f, RMSE_Ei = %.12f, RMSE_Force = %.12f, RMSE_Egroup = %.12f" %(loss_Etot ** 0.5, loss_Ei ** 0.5, loss_F ** 0.5, loss_Egroup**0.5))
    
    return loss, loss_Etot, loss_Ei, loss_F, loss_egroup
    
def valid(sample_batches, model, criterion):
    if (opt_dtype == 'float64'):
        Ei_label = Variable(sample_batches['output_energy'][:,:,:].double().to(device))
        Force_label = Variable(sample_batches['output_force'][:,:,:].double().to(device))   #[40,108,3]
        Egroup_label = Variable(sample_batches['input_egroup'].double().to(device))
        input_data = Variable(sample_batches['input_feat'].double().to(device), requires_grad=True)
        dfeat = Variable(sample_batches['input_dfeat'].double().to(device))  #[40,108,100,42,3]
        egroup_weight = Variable(sample_batches['input_egroup_weight'].double().to(device))
        divider = Variable(sample_batches['input_divider'].double().to(device))
        # Ep_label = Variable(sample_batches['output_ep'][:,:,:].double().to(device))
        if pm.dR_neigh:
            dR = Variable(sample_batches['input_dR'].double().to(device), requires_grad=True)
            dR_neigh_list = Variable(sample_batches['input_dR_neigh_list'].to(device))
            Ri = Variable(sample_batches['input_Ri'].double().to(device), requires_grad=True)
            Ri_d = Variable(sample_batches['input_Ri_d'].to(device))

    elif (opt_dtype == 'float32'):
        Ei_label = Variable(sample_batches['output_energy'][:,:,:].float().to(device))
        Force_label = Variable(sample_batches['output_force'][:,:,:].float().to(device))   #[40,108,3]
        Egroup_label = Variable(sample_batches['input_egroup'].float().to(device))
        input_data = Variable(sample_batches['input_feat'].float().to(device), requires_grad=True)
        dfeat = Variable(sample_batches['input_dfeat'].float().to(device))  #[40,108,100,42,3]
        egroup_weight = Variable(sample_batches['input_egroup_weight'].float().to(device))
        divider = Variable(sample_batches['input_divider'].float().to(device))
        # Ep_label = Variable(sample_batches['output_ep'][:,:,:].float().to(device))
        if pm.dR_neigh:
            dR = Variable(sample_batches['input_dR'].float().to(device), requires_grad=True)
            dR_neigh_list = Variable(sample_batches['input_dR_neigh_list'].to(device))
            Ri = Variable(sample_batches['input_Ri'].double().to(device), requires_grad=True)
            Ri_d = Variable(sample_batches['input_Ri_d'].to(device))

    else:
        error("train(): unsupported opt_dtype %s" %opt_dtype)
        raise RuntimeError("train(): unsupported opt_dtype %s" %opt_dtype)

    neighbor = Variable(sample_batches['input_nblist'].int().to(device))  # [40,108,100]
    natoms_img = Variable(sample_batches['natoms_img'].int().to(device))  # [40,108,100]

    error=0
    atom_number = Ei_label.shape[1]
    Etot_label = torch.sum(Ei_label, dim=1)

    # model.train()
    model.eval()

    if opt_dp:
        Etot_predict, Ei_predict, Force_predict = model(Ri, Ri_d, dR_neigh_list, natoms_img, egroup_weight, divider)
    else:
        Etot_predict, Ei_predict, Force_predict = model(input_data, dfeat, neighbor, natoms_img, egroup_weight, divider)
    
    Egroup_predict = torch.zeros_like(Ei_predict)

    if pm.kfnn_trainEgroup:
        Egroup_predict = model.get_egroup(Ei_predict,egroup_weight,divider)

    # Egroup_predict = model.get_egroup(Ei_predict, egroup_weight, divider) 

    # the logic is the same as training.
    """
    loss_F = criterion(Force_predict, Force_label)
    loss_Etot = criterion(Etot_predict, Etot_label)
    loss_Ei = criterion(Ei_predict, Ei_label)
    """

    loss_Etot = torch.zeros([1,1],device=device)
    loss_Ei = torch.zeros([1,1],device=device)
    loss_F = torch.zeros([1,1],device = device)
    loss_egroup = torch.zeros([1,1],device = device)

    # update loss with repsect to the data used
    if pm.kfnn_trainEi:
        loss_Ei = criterion(Ei_predict, Ei_label)
    
    if pm.kfnn_trainEtot:
        loss_Etot = criterion(Etot_predict, Etot_label)

    if pm.kfnn_trainForce:
        loss_F = criterion(Force_predict, Force_label)

    if pm.kfnn_trainEgroup:
        loss_egroup = criterion(Egroup_label,Egroup_predict)


    error = float(loss_F.item()) + float(loss_Etot.item()) + float(loss_Ei.item()) + float(loss_egroup.item())

    return error, loss_Etot, loss_Ei, loss_F, loss_egroup

def sec_to_hms(seconds):
    m, s = divmod(seconds, 60)
    h, m = divmod(m, 60)
    return "%02d:%02d:%02d" % (h, m, s)

# implement a linear scheduler
def LinearLR(optimizer, base_lr, target_lr, total_epoch, cur_epoch):
    lr = base_lr - (base_lr - target_lr) * (float(cur_epoch) / float(total_epoch))
    for param_group in optimizer.param_groups:
        param_group['lr'] = lr

# ==========================part1:打印参数 && 数据读取==========================

momentum = opt_momentum
REGULAR_wd = opt_regular_wd
n_epoch = opt_epochs
LR_base = opt_lr
LR_gamma = opt_gamma
LR_step = opt_step
batch_size = opt_batch_size 

if (opt_follow_mode == True):
    opt_model_file = opt_model_dir+opt_net_cfg+'.pt'

info("Training: session = %s" %opt_session_name)
info("Training: run_id = %s" %opt_run_id)
info("Training: journal_cycle = %d" %opt_journal_cycle)
info("Training: follow_mode = %s" %opt_follow_mode)
info("Training: recover_mode = %s" %opt_recover_mode)
info("Training: network = %s" %opt_net_cfg)
info("Training: model_dir = %s" %opt_model_dir)
info("Training: model_file = %s" %opt_model_file)
info("Training: activation = %s" %opt_act)
info("Training: optimizer = %s" %opt_optimizer)
info("Training: momentum = %.16f" %momentum)
info("Training: REGULAR_wd = %.16f" %REGULAR_wd)
info("Training: scheduler = %s" %opt_scheduler)
info("Training: n_epoch = %d" %n_epoch)
info("Training: LR_base = %.16f" %LR_base)
info("Training: LR_gamma = %.16f" %LR_gamma)
info("Training: LR_step = %d" %LR_step)
info("Training: batch_size = %d" %batch_size)

# scheduler specific options
info("Scheduler: opt_LR_milestones = %s" %opt_LR_milestones)
info("Scheduler: opt_LR_patience = %s" %opt_LR_patience)
info("Scheduler: opt_LR_cooldown = %s" %opt_LR_cooldown)
info("Scheduler: opt_LR_total_steps = %s" %opt_LR_total_steps)
info("Scheduler: opt_LR_max_lr = %s" %opt_LR_max_lr)
info("Scheduler: opt_LR_min_lr = %s" %opt_LR_min_lr)
info("Scheduler: opt_LR_T_max = %s" %opt_LR_T_max)
info("scheduler: opt_autograd = %s" %opt_autograd)

#======================== loading data =======================================

train_data_path = pm.train_data_path
torch_train_data = get_torch_data(train_data_path)

valid_data_path=pm.test_data_path
torch_valid_data = get_torch_data(valid_data_path)

# ===================for scaler feature and dfeature==========================

"""
    Scaling for more than 1 type of elements, each of which owns a single scaler
    All scalers are saved in the directory presrcibed by opt_session_dir   
"""

def scaleMultiElement():

    """
        scaling for multiple element
    """
    scaler = []  
    itype_index =[] # index for each type of element

    if pm.is_scale:
        if pm.use_storage_scaler:
            for i in range(pm.ntypes):
                scaler.append(load('scaler_{}.pkl'.format(pm.atomType[i])))
                itype_index.append(np.where(torch_train_data.itype == pm.atomType[i])[0])
                torch_train_data.feat[itype_index[i]]=scaler[i].transform(torch_train_data.feat[itype_index[i]])
        else:

            """
                is this correct? 
            """
            for i in range(pm.ntypes):
                
                #below can be wrong. Use .copy() 
                scaler.append(MinMaxScaler())
                
                itype_index.append(np.where(torch_train_data.itype == pm.atomType[i])[0])
                torch_train_data.feat[itype_index[i]]=scaler[i].fit_transform(torch_train_data.feat[itype_index[i]])

        for i in range(pm.ntypes):
            dfeat_tmp = torch_train_data.dfeat[itype_index[i]]
            dfeat_tmp = dfeat_tmp.transpose(0, 1, 3, 2)
            dfeat_tmp = dfeat_tmp * scaler[i].scale_
            dfeat_tmp = dfeat_tmp.transpose(0, 1, 3, 2)
            torch_train_data.dfeat[itype_index[i]] = dfeat_tmp

        if pm.storage_scaler:
            for i in range(pm.ntypes):
                output_name = opt_session_dir+'scaler_{}.pkl'.format(pm.atomType[i])
                #dump(scaler[i], output_name)
                pickle.dump(scaler[i],open(output_name,"wb"))

        itype_index = []

        for i in range(pm.ntypes):
            itype_index.append(np.where(torch_valid_data.itype == pm.atomType[i])[0])
            
            torch_valid_data.feat[itype_index[i]] = scaler[i].transform(torch_valid_data.feat[itype_index[i]])

            dfeat_tmp = torch_valid_data.dfeat[itype_index[i]]
            dfeat_tmp = dfeat_tmp.transpose(0, 1, 3, 2)
            dfeat_tmp = dfeat_tmp * scaler[i].scale_
            dfeat_tmp = dfeat_tmp.transpose(0, 1, 3, 2)
            torch_valid_data.dfeat[itype_index[i]] = dfeat_tmp
    """
    for item in scaler:
        print (item.scale_)
    """
# below only works for a single element

"""        
    For now, fortran inference code only supports 1 type of element. 
"""
    
"""
scaleMultiElement() 
"""

scaler = None

if pm.is_scale:
    # use the old scaler file 
    if pm.use_storage_scaler:
        print("loading scaler from file")
        scaler_path = opt_session_dir + 'scaler.pkl'
        scaler = load(scaler_path) 

        print("transforming feat with loaded scaler")
        torch_train_data.feat=scaler.transform(torch_train_data.feat)
    else:
        # generate new 
        print("using new scaler")
        scaler=MinMaxScaler()
        torch_train_data.feat = scaler.fit_transform(torch_train_data.feat)
        torch_valid_data.feat = scaler.transform(torch_valid_data.feat)

        if pm.storage_scaler:
            #pickle.dump(scaler, open("./scaler.pkl",'wb'))
            pickle.dump(scaler, open(opt_session_dir+"scaler.pkl",'wb'))
            print ("scaler.pkl saved to:",opt_session_dir)
    
    #atom index within this image, neighbor index, feature index, spatial dimension   

    if pm.is_dfeat_sparse == False: 
        
        # no direct scaling if sparse dfeat is used  
        dfeat_tmp = torch_train_data.dfeat
        dfeat_tmp = dfeat_tmp.transpose(0, 1, 3, 2)
        dfeat_tmp = dfeat_tmp * scaler.scale_
        dfeat_tmp = dfeat_tmp.transpose(0, 1, 3, 2)
        torch_train_data.dfeat = dfeat_tmp

        # save scaler.pkl in the prescribed directory 

        dfeat_tmp = torch_valid_data.dfeat
        dfeat_tmp = dfeat_tmp.transpose(0, 1, 3, 2)
        dfeat_tmp = dfeat_tmp * scaler.scale_ 
        dfeat_tmp = dfeat_tmp.transpose(0, 1, 3, 2)
        torch_valid_data.dfeat = dfeat_tmp

"""
    Below, only training set itself is shuffled. Need to shuffle the whole data set 
    to avoid dependence between training and validation sets. 
"""

"""
    dense dfeat
"""

loader_train = Data.DataLoader(torch_train_data, batch_size=batch_size, shuffle=False)

if opt_dp:
    davg, dstd, ener_shift = torch_train_data.get_stat(image_num=10)
    stat = [davg, dstd, ener_shift]
    np.save("./davg.npy", davg)
    np.save("./dstd.npy", dstd)
    np.save("./ener_shift", ener_shift)

loader_valid = Data.DataLoader(torch_valid_data, batch_size=batch_size, shuffle=False)

info("feat arrays loaded")

"""
    loading sparse dfeat for training and testing     
"""

dfeat_sparse = dfeat_raw( input_dfeat_record_path_train = pm.f_train_dfeat, 
                          input_feat_path_train = pm.f_train_feat,
                          input_natoms_path_train = pm.f_train_natoms,

                          input_dfeat_record_path_valid = pm.f_test_dfeat, 
                          input_feat_path_valid = pm.f_test_feat,
                          input_natoms_path_valid = pm.f_test_natoms,

                          scaler = scaler)

dfeat_sparse.load()  

info("dfeat arrays loaded")

"""
dfeat_train = dfeat_raw(input_dfeat_record_path = pm.f_train_dfeat, 
                        input_feat_path = pm.f_train_feat,
                        input_natoms_path = pm.f_train_natoms,
                        scaler = scaler)

dfeat_train.load()

dfeat_valid = dfeat_raw(input_dfeat_record_path = pm.f_test_dfeat, 
                        input_feat_path = pm.f_test_feat,
                        input_natoms_path = pm.f_test_natoms,
                        scaler = scaler)

dfeat_valid.load() 
"""


# if torch.cuda.device_count() > 1:
    # model = nn.DataParallel(model)

# os.environ['CUDA_VISIBLE_DEVICES'] = '0,1,2,3'
# torch.distributed.init_process_group(backend='nccl', init_method='tcp://localhost:23457', rank=0, world_size=1)

# ========================== part2:配置选择 ==========================
patience = 100000

#data_scalers = DataScalers(f_ds=pm.f_data_scaler, f_feat=pm.f_train_feat, load=True)

"""
    choosing model
"""

if opt_dp:
    model = DP(opt_net_cfg, opt_act, device, stat, opt_magic)
else:
    model = MLFFNet(device)

model.to(device)

start_epoch = 1

"""
    load model parameters
"""

if (opt_recover_mode == True):
    if (opt_session_name == ''):
        raise RuntimeError("you must run follow-mode from an existing session")
    opt_latest_file = opt_model_dir+'better.pt'
    checkpoint = torch.load(opt_latest_file,map_location=device)
    model.load_state_dict(checkpoint['model'])
    start_epoch = checkpoint['epoch'] + 1

#if torch.cuda.device_count() > 1:
#    model = nn.DataParallel(model)

model_parameters = model.parameters()

if (opt_optimizer == 'SGD'):
    optimizer = optim.SGD(model_parameters, lr=LR_base, momentum=momentum, weight_decay=REGULAR_wd)
elif (opt_optimizer == 'ASGD'):
    optimizer = optim.ASGD(model_parameters, lr=LR_base, weight_decay=REGULAR_wd)
elif (opt_optimizer == 'RPROP'):
    optimizer = optim.Rprop(model_parameters, lr=LR_base, weight_decay = REGULAR_wd)
elif (opt_optimizer == 'RMSPROP'):
    optimizer = optim.RMSprop(model_parameters, lr=LR_base, weight_decay=REGULAR_wd, momentum=momentum)
elif (opt_optimizer == 'ADAG'):
    optimizer = optim.Adagrad(model_parameters, lr=LR_base, weight_decay=REGULAR_wd)
elif (opt_optimizer == 'ADAD'):
    optimizer = optim.Adadelta(model_parameters, lr=LR_base, weight_decay=REGULAR_wd)
elif (opt_optimizer == 'ADAM'):
    optimizer = optim.Adam(model_parameters, lr=LR_base, weight_decay = REGULAR_wd)
elif (opt_optimizer == 'ADAMW'):
    optimizer = optim.AdamW(model_parameters, lr=LR_base)
elif (opt_optimizer == 'ADAMAX'):
    optimizer = optim.Adamax(model_parameters, lr=LR_base, weight_decay=REGULAR_wd)
elif (opt_optimizer == 'LBFGS'):
    optimizer = optim.LBFGS(model.parameters(), lr=LR_base)
else:
    error("unsupported optimizer: %s" %opt_optimizer)
    raise RuntimeError("unsupported optimizer: %s" %opt_optimizer)


# user specific LambdaLR lambda function
lr_lambda = lambda epoch: LR_gamma ** epoch
if (opt_scheduler == 'LAMBDA'):
    scheduler = optim.lr_scheduler.LambdaLR(optimizer, lr_lambda=lr_lambda)
elif (opt_scheduler == 'STEP'):
    scheduler = optim.lr_scheduler.StepLR(optimizer, step_size=LR_step, gamma=LR_gamma)
elif (opt_scheduler == 'MSTEP'):
    scheduler = optim.lr_scheduler.MultiStepLR(optimizer, milestones=opt_LR_milestones, gamma=LR_gamma)
elif (opt_scheduler == 'EXP'):
    scheduler = optim.lr_scheduler.ExponentialLR(optimizer, gamma=LR_gamma)
elif (opt_scheduler == 'NONE'):
    pass
else:
    error("unsupported scheduler: %s" %opt_schedler)
    raise RuntimeError("unsupported scheduler: %s" %opt_scheduler)

# ==========================part3:模型training==========================

if pm.use_GKalman == True:
    Gkalman = GKalmanFilter(model, kalman_lambda=0.98, kalman_nue=0.99870, device=device)
if pm.use_LKalman == True:
    Lkalman = LKalmanFilter(model, kalman_lambda=0.98, kalman_nue=0.99870, device=device, nselect=opt_nselect, groupsize=opt_groupsize, blocksize=opt_blocksize, fprefactor=opt_fprefactor)
if pm.use_SKalman == True:
    Skalman = SKalmanFilter(model, kalman_lambda=0.98, kalman_nue=0.99870, device=device)

min_loss = np.inf
iter = 1
epoch_print = 1 
iter_print = 1 

def test():
    """
        used to check if the loaded model is correct. 
    """
    nr_total_sample = 0
    valid_loss = 0.
    valid_loss_Etot = 0.
    valid_loss_Ei = 0.
    valid_loss_F = 0.
    valid_loss_Egroup = 0.0

    for i_batch, sample_batches in enumerate(loader_valid):
        natoms_sum = sample_batches['natoms_img'][0, 0].item()
        nr_batch_sample = sample_batches['input_feat'].shape[0]
        
        valid_error_iter, batch_loss_Etot, batch_loss_Ei, batch_loss_F, batch_loss_Egroup = valid(sample_batches, model, nn.MSELoss())

        # n_iter = (epoch - 1) * len(loader_valid) + i_batch + 1
        valid_loss += valid_error_iter * nr_batch_sample

        valid_loss_Etot += batch_loss_Etot * nr_batch_sample
        valid_loss_Ei += batch_loss_Ei * nr_batch_sample
        valid_loss_F += batch_loss_F * nr_batch_sample
        valid_loss_Egroup += batch_loss_Egroup * nr_batch_sample

        nr_total_sample += nr_batch_sample
        
    valid_loss /= nr_total_sample
    valid_loss_Etot /= nr_total_sample
    valid_loss_Ei /= nr_total_sample
    valid_loss_F /= nr_total_sample
    valid_loss_Egroup /= nr_total_sample

    valid_RMSE_Etot = valid_loss_Etot ** 0.5
    valid_RMSE_Ei = valid_loss_Ei ** 0.5
    valid_RMSE_F = valid_loss_F ** 0.5
    valid_RMSE_Egroup = valid_loss_Egroup ** 0.5

    print("valid_RMSE_Etot",valid_RMSE_Etot)
    print("valid_RMSE_Ei",valid_RMSE_Ei)
    print("valid_RMSE_F",valid_RMSE_F)
    print("valid_RMSE_Egroup",valid_RMSE_Egroup)

    return 

#=================================== training ==========================================

for epoch in range(start_epoch, n_epoch + 1):
    timeEpochStart = time.time()
    if (epoch == n_epoch):
        last_epoch = True
    else:
        last_epoch = False
    lr = optimizer.param_groups[0]['lr']

    info("<-------------------------  epoch %d (lr=%.16f) ------------------------->" %(epoch, lr))
    
    nr_total_sample = 0

    loss = 0.
    loss_Etot = 0.
    loss_Ei = 0.
    loss_F = 0.
    loss_Egroup = 0.0
    

    for i_batch, sample_batches in enumerate(loader_train):
        nr_batch_sample = sample_batches['input_feat'].shape[0]

        global_step = (epoch - 1) * len(loader_train) + i_batch * nr_batch_sample
        real_lr = adjust_lr(global_step)

        for param_group in optimizer.param_groups:
            param_group['lr'] = real_lr * (pm.batch_size ** 0.5)
        
        natoms_sum = sample_batches['natoms_img'][0, 0].item()
        

        # call transform 
        if pm.is_dfeat_sparse == True:
            #sample_batches['input_dfeat']  = dfeat_train.transform(i_batch)
            sample_batches['input_dfeat']  = dfeat_sparse.transform(i_batch,"train")

        if pm.use_GKalman == True:
            real_lr = 0.001
            batch_loss, batch_loss_Etot, batch_loss_Ei, batch_loss_F, batch_loss_Egroup = \
                train_kalman(sample_batches, model, Gkalman, nn.MSELoss(), last_epoch, real_lr)
        elif pm.use_LKalman == True:
            real_lr = 0.001
            batch_loss, batch_loss_Etot, batch_loss_Ei, batch_loss_F, batch_loss_Egroup = \
                train_kalman(sample_batches, model, Lkalman, nn.MSELoss(), last_epoch, real_lr)
        elif pm.use_SKalman == True:
            real_lr = 0.001
            batch_loss, batch_loss_Etot, batch_loss_Ei, batch_loss_F, batch_loss_Egroup = \
                train_kalman(sample_batches, model, Skalman, nn.MSELoss(), last_epoch, real_lr)
        else:
            # pass
            batch_loss, batch_loss_Etot, batch_loss_Ei, batch_loss_F = \
                train(sample_batches, model, optimizer, nn.MSELoss(), last_epoch, real_lr)
        
        iter = iter + 1
        f_err_log = opt_session_dir+'iter_loss.dat'
        
        if iter == 1:
            fid_err_log = open(f_err_log, 'w')
            fid_err_log.write('iter\t loss\t RMSE_Etot\t RMSE_Ei\t RMSE_F\t RMSE_Eg\n')
        if iter % iter_print == 0:
            fid_err_log = open(f_err_log, 'a')
            fid_err_log.write('%d %e %e %e %e %e \n'%(iter, batch_loss, math.sqrt(batch_loss_Etot)/natoms_sum, math.sqrt(batch_loss_Ei), math.sqrt(batch_loss_F), math.sqrt(batch_loss_Egroup)))
        else:
            pass
        
        loss += batch_loss.item() * nr_batch_sample
        loss_Etot += batch_loss_Etot.item() * nr_batch_sample
        loss_Ei += batch_loss_Ei.item() * nr_batch_sample
        loss_F += batch_loss_F.item() * nr_batch_sample

        loss_Egroup += batch_loss_Egroup.item() * nr_batch_sample 

        nr_total_sample += nr_batch_sample
        
    #update pre-factor 
    #global_prefac_Ei *= decay_rate
    #global_prefac_F  *= decay_rate 
        
    #print ("Ei prefac:", global_prefac_Ei, ", Force prefac:", global_prefac_F)

    # epoch loss update
    loss /= nr_total_sample
    loss_Etot /= nr_total_sample
    loss_Ei /= nr_total_sample
    loss_F /= nr_total_sample
    loss_Egroup /= nr_total_sample


    RMSE_Etot = loss_Etot ** 0.5
    RMSE_Ei = loss_Ei ** 0.5
    RMSE_F = loss_F ** 0.5
    RMSE_Egroup = loss_Egroup ** 0.5 

    info("epoch_loss = %.10f (RMSE_Etot = %.12f, RMSE_Ei = %.12f, RMSE_F = %.12f, RMSE_Eg = %.12f)" \
        %(loss, RMSE_Etot, RMSE_Ei, RMSE_F, RMSE_Egroup))

    epoch_err_log = opt_session_dir+'epoch_loss.dat'

    if epoch == 1:
        f_epoch_err_log = open(epoch_err_log, 'w')
        f_epoch_err_log.write('epoch\t loss\t RMSE_Etot\t RMSE_Ei\t RMSE_F\t RMSE_Eg\n')

    if epoch % epoch_print  == 0:
        f_epoch_err_log = open(epoch_err_log, 'a')
        f_epoch_err_log.write('%d %e %e %e %e %e \n'%(epoch, loss, RMSE_Etot, RMSE_Ei, RMSE_F, RMSE_Egroup))

    if (opt_scheduler == 'OC'):
        pass
    elif (opt_scheduler == 'PLAT'):
        scheduler.step(loss)
    elif (opt_scheduler == 'LR_INC'):
        LinearLR(optimizer=optimizer, base_lr=LR_base, target_lr=opt_LR_max_lr, total_epoch=n_epoch, cur_epoch=epoch)
    elif (opt_scheduler == 'LR_DEC'):
        LinearLR(optimizer=optimizer, base_lr=LR_base, target_lr=opt_LR_min_lr, total_epoch=n_epoch, cur_epoch=epoch)
    elif (opt_scheduler == 'NONE'):
        pass
    else:
        scheduler.step()

    if opt_save_model == True: 
        state = {'model': model.state_dict(),'optimizer':optimizer.state_dict(),'epoch':epoch, 'loss': loss}
        file_name = opt_model_dir + 'latest.pt'
        if epoch % 10 == 0:
            file_name = opt_model_dir + str(epoch) + '.pt'
        torch.save(state, file_name)

    # update tensorboard
    if ((opt_journal_cycle > 0) and ((epoch) % opt_journal_cycle == 0)):
        if (writer is not None):
            writer.add_scalar('learning_rate', lr, epoch)
            writer.add_scalar('train_loss', loss, epoch)
            writer.add_scalar('train_RMSE_Etot', RMSE_Etot, epoch)
            writer.add_scalar('train_RMSE_F', RMSE_F, epoch)

# ==========================part4:模型validation==========================
    if epoch >=  1:
        nr_total_sample = 0
        valid_loss = 0.
        valid_loss_Etot = 0.
        valid_loss_Ei = 0.
        valid_loss_F = 0.
        valid_loss_Egroup = 0.0

        for i_batch, sample_batches in enumerate(loader_valid):
            natoms_sum = sample_batches['natoms_img'][0, 0].item()
            nr_batch_sample = sample_batches['input_feat'].shape[0]
            
            # call transform() when dfeat_sparse = true 
            if pm.is_dfeat_sparse == True:
                #sample_batches['input_dfeat']  = dfeat_valid.transform(i_batch)
                sample_batches['input_dfeat']  = dfeat_sparse.transform(i_batch,"valid")

            valid_error_iter, batch_loss_Etot, batch_loss_Ei, batch_loss_F, batch_loss_Egroup = valid(sample_batches, model, nn.MSELoss())

            # n_iter = (epoch - 1) * len(loader_valid) + i_batch + 1
            valid_loss += valid_error_iter * nr_batch_sample

            valid_loss_Etot += batch_loss_Etot * nr_batch_sample
            valid_loss_Ei += batch_loss_Ei * nr_batch_sample
            valid_loss_F += batch_loss_F * nr_batch_sample
            valid_loss_Egroup += batch_loss_Egroup * nr_batch_sample

            nr_total_sample += nr_batch_sample

            f_err_log = opt_session_dir+'iter_loss_valid.dat'
            if iter == 1:
                fid_err_log = open(f_err_log, 'w')
                fid_err_log.write('iter\t loss\t RMSE_Etot\t RMSE_Ei\t RMSE_F\t lr\n')
            if iter % iter_print == 0:
                fid_err_log = open(f_err_log, 'a')
                fid_err_log.write('%d %e %e %e %e %e \n'%(iter, batch_loss, math.sqrt(batch_loss_Etot)/natoms_sum, math.sqrt(batch_loss_Ei), math.sqrt(batch_loss_F), real_lr))
            else:
                pass

        # epoch loss update
        valid_loss /= nr_total_sample
        valid_loss_Etot /= nr_total_sample
        valid_loss_Ei /= nr_total_sample
        valid_loss_F /= nr_total_sample
        valid_loss_Egroup /= nr_total_sample

        valid_RMSE_Etot = valid_loss_Etot ** 0.5
        valid_RMSE_Ei = valid_loss_Ei ** 0.5
        valid_RMSE_F = valid_loss_F ** 0.5
        valid_RMSE_Egroup = valid_loss_Egroup ** 0.5
        
        info("valid_loss = %.10f (valid_RMSE_Etot = %.12f, valid_RMSE_Ei = %.12f, valid_RMSE_F = %.12f, valid_RMSE_Egroup = %.12f)" \
             %(valid_loss, valid_RMSE_Etot, valid_RMSE_Ei, valid_RMSE_F, valid_RMSE_Egroup))

        f_err_log =  opt_session_dir + 'epoch_loss_valid.dat'
        if not os.path.exists(f_err_log):
            fid_err_log = open(f_err_log, 'w')
            fid_err_log.write('epoch\t valid_RMSE_Etot\t valid_RMSE_Ei\t valid_RMSE_F\t valid_RMSE_Eg \n')
        if epoch % epoch_print == 0:
            fid_err_log = open(f_err_log, 'a')
            fid_err_log.write('%d %e %e %e %e\n'%(epoch, valid_RMSE_Etot, valid_RMSE_Ei, valid_RMSE_F, valid_RMSE_Egroup))
        
        if valid_loss < min_loss:
            min_loss = valid_loss
            works_epoch = 0
            name = opt_model_dir  + 'better.pt'
            # state = {'model': model.state_dict(), 'optimizer':optimizer.state_dict(),'epoch': epoch}
            state = {'model': model.state_dict(), 'epoch': epoch}
            torch.save(state, name)
            print('saving model to {}'.format(name))
        else:
            works_epoch += 1
            if works_epoch > patience:
                name = opt_model_dir + 'MLFFNet.pt'
                state = {'model': model.state_dict(), 'optimizer':optimizer.state_dict(),'epoch': epoch}
                torch.save(state, name)
                print("Early stopping")
                break

    timeEpochEnd = time.time()
    #info("time of epoch ", epoch, ":", timeEpochEnd - timeEpochStart, " s")
    print ("time of epoch ", epoch, ":", timeEpochEnd - timeEpochStart, " s")
    
if (writer is not None):
    writer.close()
    if (opt_wandb is True):
        wandb_run.finish()


