import tensorflow as tf
import numpy as np
from alpha import alpha_model
from alpha_loss import alpha_loss
import generate_data
import preprocess_data
import random
import os

def train(batch_size_per_replica,EPOCHS,img_train_info,class_train_info,img_train_path,img_shape = (640,640),standard_scale=(19360,66930)):

   #get number of sample m
   m = len(list(img_train_info.keys()))

   #define strategy
   strategy = tf.distribute.MirroredStrategy(cross_device_ops=tf.distribute.HierarchicalCopyAllReduce())

   #dataset size
   global_batch_size = batch_size_per_replica * strategy.num_replicas_in_sync
   buffer_size = global_batch_size * 2

   #total step per epochs
   total_step_per_epoch = int(m/buffer_size)

   #define model,loss,optimizer
   with strategy.scope():

      #define loss object
      loss_object = alpha_loss()

      #define compute loss
      def compute_loss(labels,predictions):

         #large
         large_obj_loss = loss_object(labels[0],predictions[0])

         #medium
         medium_obj_loss = loss_object(labels[1],predictions[1])

         #small
         small_obj_loss = loss_object(labels[2],predictions[2])

         #total loss
         total_loss = large_obj_loss + medium_obj_loss + small_obj_loss

         return total_loss

      #define optimizer
      optimizer = tf.keras.optimizers.Adam()

      #define model
      model = alpha_model()


   #train
   for i  in range(EPOCHS):

      total_loss = 0.0

      for step in range(total_step_per_epoch):

         #get data 
         train_images, train_labels = get_gt_data(buffer_size,img_train_info,class_train_info,img_train_path,img_shape,standard_scale)

         #normalize the image to 0 to 1
         train_images = train_images/ np.float64(255)

         # Create Datasets from the batches
         train_dataset = tf.data.Dataset.from_tensor_slices((train_images, train_labels)).shuffle(buffer_size).batch(global_batch_size)

         #create distributed dataset
         train_dist_dataset = strategy.experimental_distribute_dataset(train_dataset)

         #Do training
         for batch in train_dist_dataset:

            total_loss = total_loss + distributed_train_step(batch)

      print(f"Epoch {i+1} , Loss: {total_loss}")
      

@tf.function
def distributed_train_step(data_inputs):

   per_replica_losses = strategy.run(train_step,args=(data_inputs,))

   return strategy.reduce(tf.distribute.ReduceOp.SUM,per_replica_losses,axis=None)


def train_step(inputs):

   images,labels = inputs

   with tf.GradientTape() as tape:

      predictions = model(images,train_flag=True)
      
      loss = compute_loss(labels,predictions)

   gradients = tape.gradient(loss,model.trainable_variables)

   optimizer.apply_gradients(zip(gradients,model.trainable_variables))

   return loss




